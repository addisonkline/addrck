import smtplib
from smtplib import SMTP
from unittest.mock import Mock, call

import dns.resolver
import dns.rrset
import pytest

from addrck import cli

SENDER = "sender@example.org"
RECIPIENT = "person@example.com"
PROBE = "probe@example.com"


@pytest.fixture
def smtp():
    connection = Mock(spec=SMTP)
    connection.ehlo.return_value = (250, b"hello")
    connection.mail.return_value = (250, b"sender accepted")
    connection.rcpt.side_effect = [(250, b"recipient accepted"), (550, b"unknown mailbox")]
    connection.rset.return_value = (250, b"reset")
    return connection


@pytest.fixture
def exchanger_setup(monkeypatch, smtp):
    mx = dns.rrset.from_text(
        "example.com", 60, "IN", "MX", "10 primary.example.com.", "20 backup.example.com.",
    )
    monkeypatch.setattr(cli, "find_mail_exchangers", Mock(return_value=list(mx)))
    monkeypatch.setattr(cli, "generate_invalid_address", Mock(return_value=PROBE))
    connect = Mock(return_value=smtp)
    monkeypatch.setattr(cli, "connect_to_exchanger", connect)
    return connect


def test_connection_parameters(monkeypatch, smtp):
    constructor = Mock(return_value=smtp)
    monkeypatch.setattr(cli.smtplib, "SMTP", constructor)

    assert cli.connect_to_exchanger("mx.example.com", 7) is smtp
    constructor.assert_called_once_with("mx.example.com", port=25, timeout=7.0)


@pytest.mark.parametrize("error", [
    OSError("unreachable"), TimeoutError("timeout"), smtplib.SMTPConnectError(421, b"unavailable"),
])
def test_connection_failure(monkeypatch, error):
    monkeypatch.setattr(cli.smtplib, "SMTP", Mock(side_effect=error))
    assert cli.connect_to_exchanger("mx.example.com", 5) is None


def test_verification_command_order_and_result(exchanger_setup, smtp):
    assert cli.verify_email(RECIPIENT, SENDER, 5) == (
        250, b"recipient accepted", 550, b"unknown mailbox",
    )
    cli.find_mail_exchangers.assert_called_once_with("example.com")
    cli.generate_invalid_address.assert_called_once_with(RECIPIENT)
    exchanger_setup.assert_called_once_with("primary.example.com", 5)
    # Exact calls also ensure DATA/sendmail are never used.
    assert smtp.mock_calls == [
        call.ehlo(), call.mail(SENDER), call.rcpt(RECIPIENT), call.rset(),
        call.mail(SENDER), call.rcpt(PROBE), call.close(),
    ]


def test_unreachable_primary_tries_backup(exchanger_setup, smtp):
    exchanger_setup.side_effect = [None, smtp]
    cli.verify_email(RECIPIENT, SENDER, 9)
    assert exchanger_setup.call_args_list == [
        call("primary.example.com", 9), call("backup.example.com", 9),
    ]
    smtp.close.assert_called_once_with()


def test_all_exchangers_unreachable(exchanger_setup, smtp):
    exchanger_setup.return_value = None
    with pytest.raises(RuntimeError, match="no reachable mail exchangers"):
        cli.verify_email(RECIPIENT, SENDER, 5)
    assert exchanger_setup.call_count == 2
    smtp.close.assert_not_called()


@pytest.mark.parametrize("stage, message, expected_rcpts", [
    ("ehlo", "SMTP greeting rejected", 0),
    ("first_mail", "sender rejected", 0),
    ("rset", "SMTP reset rejected", 1),
    ("second_mail", "sender rejected for probe", 1),
])
def test_command_rejection_closes_connection(
    exchanger_setup, smtp, stage, message, expected_rcpts,
):
    if stage == "first_mail":
        smtp.mail.return_value = (550, b"rejected")
    elif stage == "second_mail":
        smtp.mail.side_effect = [(250, b"ok"), (550, b"rejected")]
    else:
        getattr(smtp, stage).return_value = (550, b"rejected")

    with pytest.raises(RuntimeError, match=message):
        cli.verify_email(RECIPIENT, SENDER, 5)

    assert smtp.rcpt.call_count == expected_rcpts
    smtp.close.assert_called_once_with()
    assert smtp.mock_calls[-1] == call.close()


@pytest.mark.parametrize("stage", ["ehlo", "first_mail", "real_rcpt", "rset", "second_mail", "probe_rcpt"])
@pytest.mark.parametrize("error", [OSError("socket failed"), smtplib.SMTPServerDisconnected("disconnected")])
def test_exchange_errors_close_connection(exchanger_setup, smtp, stage, error):
    if stage == "first_mail":
        smtp.mail.side_effect = error
    elif stage == "second_mail":
        smtp.mail.side_effect = [(250, b"ok"), error]
    elif stage == "real_rcpt":
        smtp.rcpt.side_effect = error
    elif stage == "probe_rcpt":
        smtp.rcpt.side_effect = [(250, b"ok"), error]
    else:
        getattr(smtp, stage).side_effect = error

    with pytest.raises(RuntimeError, match="SMTP exchange failed with primary.example.com") as exc:
        cli.verify_email(RECIPIENT, SENDER, 5)

    assert exc.value.__cause__ is error
    smtp.close.assert_called_once_with()
    assert smtp.mock_calls[-1] == call.close()


@pytest.mark.parametrize("real_code, fake_code", [(550, 550), (450, 550), (250, 250), (250, 450)])
def test_recipient_responses_pass_through(exchanger_setup, smtp, real_code, fake_code):
    smtp.rcpt.side_effect = [(real_code, b"real"), (fake_code, b"probe")]
    assert cli.verify_email(RECIPIENT, SENDER, 5) == (real_code, b"real", fake_code, b"probe")
    smtp.close.assert_called_once_with()


def test_implicit_mx_can_be_used_by_verification(monkeypatch, smtp):
    # Exercise the actual resolver-to-verifier boundary for the fallback path.
    address = dns.rrset.from_text("example.com", 60, "IN", "AAAA", "2001:db8::1")
    resolve = Mock(side_effect=[dns.resolver.NoAnswer(), dns.resolver.NoAnswer(), address])
    monkeypatch.setattr(cli.dns.resolver, "resolve", resolve)
    constructor = Mock(return_value=smtp)
    monkeypatch.setattr(cli.smtplib, "SMTP", constructor)

    assert cli.verify_email(RECIPIENT, SENDER, 5)[0] == 250
    constructor.assert_called_once_with("example.com", port=25, timeout=5.0)
    probe = smtp.rcpt.call_args_list[1].args[0]
    assert probe != RECIPIENT
    assert probe.endswith("@example.com")
    smtp.close.assert_called_once_with()
