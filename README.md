# addrck
simple SMTP email address verifier

## Development and tests

Use Python 3.13 or newer and uv to install the project and development dependencies:

```sh
uv sync --locked
uv run pytest
```

To include branch coverage and report uncovered lines:

```sh
uv run pytest --cov --cov-report=term-missing
```

The suite covers input validation, DNS lookup and address-record fallback, SMTP
command order and connection cleanup, and CLI output and exit statuses. DNS and
SMTP connections are mocked; tests do not contact public mail servers. An
automatic fixture rejects unmocked DNS lookups and SMTP connections.

Missing MX records fall back to the domain itself when it has A or AAAA records.
Nonexistent domains, null MX records, and domains without address records are
input errors (exit 5). Resolver failures, SMTP command failures, and unreachable
exchangers are runtime errors (exit 6). Recipient/probe reply codes determine the
remaining validation outcomes; SMTP acceptance does not guarantee delivery.

GitHub Actions runs the suite on Python 3.13 and 3.14.
