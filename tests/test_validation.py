import base64

import pytest

from addrck import cli


@pytest.mark.parametrize("address", [
    "person@example.com", "first.last+tag@example.com", "person@mail.example.com",
])
def test_valid_email_is_unchanged(address):
    assert cli.verify_email_syntax(address) == address


@pytest.mark.parametrize("address", [
    "", "person", "@example.com", "person@", "person@@example.com", "a b@example.com",
])
def test_invalid_email(address):
    with pytest.raises(ValueError, match="invalid email address"):
        cli.verify_email_syntax(address)


@pytest.mark.parametrize("timeout", [1, 5, 60])
def test_valid_timeout(timeout):
    assert cli.verify_timeout(timeout) == timeout


@pytest.mark.parametrize("timeout", [0, -1, -100])
def test_nonpositive_timeout(timeout):
    with pytest.raises(ValueError, match="timeout must be > 0 seconds"):
        cli.verify_timeout(timeout)


@pytest.mark.parametrize("domain", ["example.com", "mail.example.com"])
def test_probe_address(monkeypatch, domain):
    random_bytes = bytes(range(16))

    def randbytes(count):
        assert count == 16
        return random_bytes

    monkeypatch.setattr(cli.random, "randbytes", randbytes)
    address = cli.generate_invalid_address(f"person@{domain}")

    assert address == f"{base64.urlsafe_b64encode(random_bytes).decode()}@{domain}"
    assert cli.verify_email_syntax(address) == address
