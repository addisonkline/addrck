from unittest.mock import Mock, call

import dns.exception
import dns.resolver
import dns.rrset
import pytest

from addrck import cli


def records(record_type, *values):
    return dns.rrset.from_text("example.com", 60, "IN", record_type, *values)


def test_mx_records_sorted_by_preference(monkeypatch):
    answers = records("MX", "20 backup.example.com.", "10 primary.example.com.")
    resolve = Mock(return_value=answers)
    monkeypatch.setattr(cli.dns.resolver, "resolve", resolve)

    result = cli.find_mail_exchangers("example.com")

    assert [(mx.preference, str(mx.exchange)) for mx in result] == [
        (10, "primary.example.com."), (20, "backup.example.com."),
    ]
    resolve.assert_called_once_with("example.com", "MX")


def test_null_mx_rejects_domain_without_fallback(monkeypatch):
    resolve = Mock(return_value=records("MX", "0 ."))
    monkeypatch.setattr(cli.dns.resolver, "resolve", resolve)

    with pytest.raises(ValueError, match="does not accept email"):
        cli.find_mail_exchangers("example.com")

    resolve.assert_called_once_with("example.com", "MX")


@pytest.mark.parametrize("missing_mx", [dns.resolver.NoAnswer(), []])
@pytest.mark.parametrize("record_type, address", [
    ("A", "192.0.2.1"), ("AAAA", "2001:db8::1"),
])
def test_address_fallback_returns_usable_implicit_mx(
    monkeypatch, missing_mx, record_type, address,
):
    responses = [missing_mx]
    if record_type == "AAAA":
        responses.append(dns.resolver.NoAnswer())
    responses.append(records(record_type, address))
    resolve = Mock(side_effect=responses)
    monkeypatch.setattr(cli.dns.resolver, "resolve", resolve)

    result = cli.find_mail_exchangers("example.com")

    assert [(mx.preference, str(mx.exchange)) for mx in result] == [(0, "example.com.")]
    expected = [call("example.com", "MX"), call("example.com", "A")]
    if record_type == "AAAA":
        expected.append(call("example.com", "AAAA"))
    assert resolve.call_args_list == expected


def test_no_mx_or_address_records(monkeypatch):
    resolve = Mock(side_effect=dns.resolver.NoAnswer)
    monkeypatch.setattr(cli.dns.resolver, "resolve", resolve)

    with pytest.raises(ValueError, match="no mail exchangers or address records"):
        cli.find_mail_exchangers("example.com")

    assert resolve.call_args_list == [
        call("example.com", "MX"), call("example.com", "A"), call("example.com", "AAAA"),
    ]


@pytest.mark.parametrize("error, exception_type, message", [
    (dns.resolver.NXDOMAIN(), ValueError, "bad domain"),
    (dns.exception.Timeout(), RuntimeError, "DNS lookup failed"),
    (dns.resolver.NoNameservers(), RuntimeError, "DNS lookup failed"),
])
@pytest.mark.parametrize("lookup_stage", ["MX", "A", "AAAA"])
def test_resolver_errors(monkeypatch, error, exception_type, message, lookup_stage):
    missing = [dns.resolver.NoAnswer() for _ in range(("MX", "A", "AAAA").index(lookup_stage))]
    resolve = Mock(side_effect=[*missing, error])
    monkeypatch.setattr(cli.dns.resolver, "resolve", resolve)

    with pytest.raises(exception_type, match=message) as exc:
        cli.find_mail_exchangers("example.com")

    assert exc.value.__cause__ is error
