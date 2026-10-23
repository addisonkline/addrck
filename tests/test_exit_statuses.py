"""Verify numeric CLI statuses through the real DNS/SMTP orchestration."""

import smtplib
import sys
from smtplib import SMTP
from unittest.mock import Mock

import dns.exception
import dns.resolver
import dns.rrset
import pytest

from addrck import cli


@pytest.fixture
def network(monkeypatch):
    mx = dns.rrset.from_text("example.com", 60, "IN", "MX", "10 mx.example.com.")
    resolve = Mock(return_value=mx)
    smtp = Mock(spec=SMTP)
    smtp.ehlo.return_value = (250, b"hello")
    smtp.mail.return_value = (250, b"sender accepted")
    smtp.rset.return_value = (250, b"reset")
    smtp.rcpt.side_effect = [(250, b"accepted"), (550, b"no such mailbox")]
    constructor = Mock(return_value=smtp)
    monkeypatch.setattr(cli.dns.resolver, "resolve", resolve)
    monkeypatch.setattr(cli.smtplib, "SMTP", constructor)
    monkeypatch.setattr(sys, "argv", ["addrck", "sender@example.org", "person@example.com"])
    return resolve, smtp, constructor


def assert_exit(capsys, expected_status, expected_message):
    with pytest.raises(SystemExit) as exc:
        cli.run()
    assert exc.value.code == expected_status
    output = capsys.readouterr()
    if expected_status in (2, 5, 6):
        assert expected_message in output.err
        assert output.out == ""
    else:
        assert expected_message in output.out
        assert output.err == ""


@pytest.mark.parametrize("answers, status, message", [
    ([dns.resolver.NXDOMAIN()], 1, "nonexistent domain"),
    ([dns.rrset.from_text("example.com", 60, "IN", "MX", "0 .")], 1, "does not accept email"),
    ([dns.resolver.NoAnswer(), dns.resolver.NoAnswer(), dns.resolver.NoAnswer()],
     1, "no mail exchangers or address records"),
    ([dns.exception.Timeout()], 5, "DNS lookup failed"),
    ([dns.resolver.NoNameservers()], 5, "DNS lookup failed"),
    ([dns.exception.DNSException("bad response")], 6, "DNS lookup failed"),
])
def test_dns_exit_status(network, capsys, answers, status, message):
    resolve, smtp, constructor = network
    resolve.side_effect = answers
    assert_exit(capsys, status, message)
    constructor.assert_not_called()


@pytest.mark.parametrize("stage, response, status, message", [
    ("real", (250, b"ok"), 0, "likely valid"),
    ("real", (550, b"no"), 1, "likely undeliverable"),
    ("real", (450, b"later"), 5, "temporary failure"),
    ("real", (554, b"refused"), 3, "SMTP code 554"),
    ("probe", (250, b"ok"), 4, "might accept all addresses"),
    ("probe", (450, b"later"), 5, "temporary failure"),
    ("probe", (554, b"refused"), 3, "SMTP code 554 for probe"),
    ("ehlo", (450, b"later"), 5, "SMTP greeting rejected"),
    ("ehlo", (550, b"refused"), 6, "SMTP greeting rejected"),
    ("first_mail", (450, b"later"), 5, "sender rejected"),
    ("first_mail", (550, b"refused"), 6, "sender rejected"),
    ("rset", (450, b"later"), 5, "SMTP reset rejected"),
    ("rset", (550, b"refused"), 6, "SMTP reset rejected"),
    ("probe_mail", (450, b"later"), 5, "sender rejected for probe"),
    ("probe_mail", (550, b"refused"), 6, "sender rejected for probe"),
    ("real", TimeoutError("timed out"), 5, "SMTP exchange failed"),
    ("probe", smtplib.SMTPServerDisconnected("disconnected"), 5, "SMTP exchange failed"),
    ("ehlo", smtplib.SMTPResponseException(421, b"later"), 5, "SMTP code 421"),
    ("ehlo", smtplib.SMTPResponseException(554, b"refused"), 6, "SMTP code 554"),
    ("ehlo", smtplib.SMTPException("bad protocol"), 6, "SMTP exchange failed"),
])
def test_smtp_exit_status(network, capsys, stage, response, status, message):
    resolve, smtp, constructor = network
    if stage == "real":
        smtp.rcpt.side_effect = [response, (550, b"no such mailbox")]
    elif stage == "probe":
        smtp.rcpt.side_effect = [(250, b"ok"), response]
    elif stage == "first_mail":
        smtp.mail.side_effect = [response]
    elif stage == "probe_mail":
        smtp.mail.side_effect = [(250, b"ok"), response]
    elif isinstance(response, Exception):
        getattr(smtp, stage).side_effect = response
    else:
        getattr(smtp, stage).return_value = response

    assert_exit(capsys, status, message)
    smtp.close.assert_called_once_with()
    if stage == "real" and isinstance(response, tuple) and response[0] != 250:
        smtp.rset.assert_not_called()
        assert smtp.rcpt.call_count == 1


@pytest.mark.parametrize("error, status, message", [
    (TimeoutError("timed out"), 5, "no reachable mail exchangers"),
    (OSError("unreachable"), 5, "no reachable mail exchangers"),
    (smtplib.SMTPServerDisconnected("disconnected"), 5, "no reachable mail exchangers"),
    (smtplib.SMTPConnectError(421, b"later"), 5, "no reachable mail exchangers"),
    (smtplib.SMTPConnectError(554, b"refused"), 6, "no usable mail exchangers"),
    (smtplib.SMTPException("bad protocol"), 6, "no usable mail exchangers"),
])
def test_connection_exit_status(network, capsys, error, status, message):
    resolve, smtp, constructor = network
    constructor.side_effect = error
    assert_exit(capsys, status, message)
    smtp.close.assert_not_called()
