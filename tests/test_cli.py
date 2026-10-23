import sys
from unittest.mock import Mock

import pytest

from addrck import cli

SENDER = "sender@example.org"
RECIPIENT = "person@example.com"


@pytest.fixture
def verify(monkeypatch):
    verify = Mock(return_value=(250, b"real response", 550, b"probe response"))
    monkeypatch.setattr(cli, "verify_email", verify)
    return verify


def invoke(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["addrck", *args])
    with pytest.raises(SystemExit) as exc:
        cli.run()
    return exc.value.code


@pytest.mark.parametrize("real, probe, status, message, verbose_messages", [
    (250, 550, 0, "likely valid", ("real response", "probe response")),
    (550, 250, 1, "likely nonexistent", ("real response",)),
    (400, 550, 2, "temporary failure", ("real response",)),
    (450, 550, 2, "temporary failure", ("real response",)),
    (499, 550, 2, "temporary failure", ("real response",)),
    (250, 400, 2, "temporary failure", ("real response", "probe response")),
    (250, 450, 2, "temporary failure", ("real response", "probe response")),
    (250, 499, 2, "temporary failure", ("real response", "probe response")),
    (250, 250, 4, "might accept all addresses", ("real response", "probe response")),
    (251, 550, 3, "got SMTP code 251", ("real response",)),
    (399, 550, 3, "got SMTP code 399", ("real response",)),
    (500, 550, 3, "got SMTP code 500", ("real response",)),
    (554, 550, 3, "got SMTP code 554", ("real response",)),
    (250, 251, 3, "got SMTP code 251 for probe address", ("probe response",)),
    (250, 399, 3, "got SMTP code 399 for probe address", ("probe response",)),
    (250, 500, 3, "got SMTP code 500 for probe address", ("probe response",)),
    (250, 554, 3, "got SMTP code 554 for probe address", ("probe response",)),
])
@pytest.mark.parametrize("verbose", [False, True])
def test_result_classification(
    monkeypatch, capsys, verify, real, probe, status, message, verbose_messages, verbose,
):
    verify.return_value = (real, b"real response", probe, b"probe response")
    args = [SENDER, RECIPIENT, *(["--verbose"] if verbose else [])]

    assert invoke(monkeypatch, args) == status
    output = capsys.readouterr()
    assert message in output.out
    assert output.err == ""
    for response in ("real response", "probe response"):
        assert (response in output.out) == (verbose and response in verbose_messages)
    verify.assert_called_once_with(RECIPIENT, SENDER, 5)


@pytest.mark.parametrize("option", ["-t", "--timeout"])
def test_custom_timeout(monkeypatch, verify, option):
    assert invoke(monkeypatch, [SENDER, RECIPIENT, option, "12"]) == 0
    verify.assert_called_once_with(RECIPIENT, SENDER, 12)


def test_short_verbose_option(monkeypatch, capsys, verify):
    assert invoke(monkeypatch, [SENDER, RECIPIENT, "-v"]) == 0
    assert "probe response" in capsys.readouterr().out


@pytest.mark.parametrize("args, message", [
    (["bad-sender", RECIPIENT], "invalid email address: bad-sender"),
    ([SENDER, "bad-recipient"], "invalid email address: bad-recipient"),
    ([SENDER, RECIPIENT, "--timeout", "-1"], "timeout must be >= 0 seconds"),
])
def test_invalid_input_skips_verification(monkeypatch, capsys, verify, args, message):
    assert invoke(monkeypatch, args) == 5
    assert message in capsys.readouterr().out
    verify.assert_not_called()


@pytest.mark.parametrize("error, status, message", [
    (ValueError("bad domain"), 5, "invalid input: bad domain"),
    (RuntimeError("no reachable mail exchangers"), 6,
     "unexpected runtime error: no reachable mail exchangers"),
])
def test_verification_error(monkeypatch, capsys, verify, error, status, message):
    verify.side_effect = error
    assert invoke(monkeypatch, [SENDER, RECIPIENT]) == status
    assert message in capsys.readouterr().out


@pytest.mark.parametrize("args", [[], [SENDER], [SENDER, RECIPIENT, "-t", "abc"]])
def test_argument_errors(monkeypatch, capsys, verify, args):
    assert invoke(monkeypatch, args) == 2
    assert "usage: addrck" in capsys.readouterr().err
    verify.assert_not_called()


@pytest.mark.parametrize("option", ["-h", "--help"])
def test_help(monkeypatch, capsys, verify, option):
    assert invoke(monkeypatch, [option]) == 0
    output = capsys.readouterr().out
    assert "simple SMTP email address verifier" in output
    assert "--timeout" in output
    assert "default: 5" in output
    verify.assert_not_called()
