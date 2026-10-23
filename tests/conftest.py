import pytest

from addrck import cli


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Every test must supply its own DNS and SMTP responses."""
    def unexpected_network(*args, **kwargs):
        raise AssertionError("test attempted an unmocked DNS or SMTP connection")

    monkeypatch.setattr(cli.dns.resolver, "resolve", unexpected_network)
    monkeypatch.setattr(cli.smtplib, "SMTP", unexpected_network)
