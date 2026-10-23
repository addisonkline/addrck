# Development

[Documentation index](README.md)

## Set up

From a local checkout with uv installed:

```sh
uv sync --locked
uv run addrck --help
uv run pytest
```

The development dependency group contains `pytest` and `pytest-cov`. Runtime
dependencies remain separate in `pyproject.toml`. Commit `uv.lock` when changing
dependencies so other developers and CI can reproduce the environment.

## Project layout

```text
src/addrck/
    __init__.py
    cli.py                 DNS, SMTP, input validation, and CLI entry point
tests/
    conftest.py            Automatic DNS/SMTP guard
    test_validation.py     Address syntax, timeout, and generated probe
    test_dns.py            MX ordering, null MX, fallback, and resolver errors
    test_smtp.py           Connection attempts, command order, and cleanup
    test_cli.py            Arguments, output, and exit statuses
    test_exit_statuses.py  CLI statuses through actual DNS/SMTP orchestration
.github/workflows/tests.yml
pyproject.toml
uv.lock
docs/
```

The installed `addrck` command calls `addrck.cli:run`, as configured in
`pyproject.toml`. There is no `python -m addrck` entry point.

## Internal functions

All implementation functions currently live in [cli.py](../src/addrck/cli.py).
These describe the internal structure; the supported user interface is the CLI.

| Function | Responsibility |
| --- | --- |
| `verify_email_syntax(address)` | Return the unchanged address or raise `ValueError`. |
| `verify_timeout(timeout)` | Return a positive timeout or raise `ValueError`. |
| `find_mail_exchangers(domain)` | Return an ordered list of MX records, including a synthetic MX for address fallback. |
| `connect_to_exchanger(hostname, timeout)` | Connect on port 25; return an SMTP object, `None` for temporary failures, or raise `RuntimeError` for other SMTP failures. |
| `generate_invalid_address(address)` | Generate a random probe on the supplied address's domain. |
| `verify_email(recipient, sender, timeout)` | Run the DNS/SMTP check and return `(real_code, real_message, fake_code, fake_message)`. |
| `run()` | Parse arguments, validate input, classify replies, print output, and exit. |

`verify_email` and `generate_invalid_address` assume their address inputs have
already passed syntax validation. Note that `verify_email` takes the recipient
first, while the CLI takes the sender first. SMTP messages in the result tuple
are bytes.
The fake code/message are `None` when the real recipient was not accepted and
the probe was skipped.

Exit values are named in `ExitCode`. Invalid CLI input raises `ValueError` and
is reported through `parser.error()` (exit `2`). `UndeliverableDomain` is distinct
from caller errors and maps to exit `1`. `TemporaryFailure` maps to exit `5`;
other caught runtime failures map to exit `6`. See the
[validation flow](validation.md) for fallback/retry behavior and the
[usage guide](usage.md#changes-before-v010) for changes to the earlier exit codes.

## Run tests

```sh
uv run pytest
uv run pytest tests/test_dns.py
uv run pytest -k command_rejection
uv run pytest --cov --cov-report=term-missing
```

Coverage is configured in `pyproject.toml` to include the `addrck` package and
measure branches. There is currently no enforced minimum coverage percentage.
GitHub Actions runs the suite with coverage on Python 3.13 and 3.14.

The automatic fixture in `tests/conftest.py` replaces `dns.resolver.resolve` and
`smtplib.SMTP` with functions that fail on unmocked calls. Tests replace those
functions with controlled responses, or mock higher-level helpers. This guards
these network entry points; it is not a general socket sandbox.

## Making changes

Keep tests deterministic and independent of public DNS or mail servers. Use real
DNS record objects with mocked resolver calls for routing tests, and controlled
SMTP objects for protocol sequencing and exceptions. Patch random bytes when
asserting an exact generated address.

For behavior changes, add cases that exercise both the result and its failure
handling. In particular, preserve connection cleanup and ensure no message data
is sent during verification. Changes to CLI classifications should update the
parameterized CLI tests and [exit-status documentation](usage.md#exit-statuses)
together.

Before submitting changes, run the relevant tests and `git diff --check`. Run
the complete suite when changing shared validation or SMTP/DNS behavior. For
documentation changes, check relative links and confirm command examples against
the CLI without contacting real mail servers.
