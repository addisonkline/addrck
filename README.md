# addrck

addrck is a command-line email address checker. It validates address syntax,
looks up the recipient domain's mail servers, and asks an SMTP server whether it
accepts the recipient. It also checks a randomly generated address on the same
domain to help identify servers that accept every address.

The result is an estimate of whether a mailbox exists. SMTP acceptance does not
guarantee delivery, and server policies can make a check inconclusive. addrck
uses SMTP envelope commands without submitting a message.

## Quick start

You need Python 3.13 or newer, uv, a local checkout of this repository, and network
access to DNS and outbound TCP port 25. From the repository root:

```sh
uv sync --locked
uv run addrck --help
uv run addrck sender@example.org person@example.com
```

Replace the example addresses with your envelope sender and the recipient you
want to check. Argument order is **sender, then recipient**.

For additional SMTP response details and a longer socket timeout:

```sh
uv run addrck --verbose --timeout 10 sender@example.org person@example.com
```

See [installation](docs/installation.md) for a pip installation and setup without
development dependencies, and [usage](docs/usage.md) for the complete CLI reference.

## Results

addrck prints a human-readable result and exits with a status code:

| Code | Meaning |
| --- | --- |
| `0` | Recipient accepted and probe rejected with `550`: likely valid. Also used for `--help`. |
| `1` | Recipient rejected with `550`, or domain cannot receive mail: undeliverable. |
| `2` | Invalid arguments, address syntax, or timeout. |
| `3` | SMTP recipient/probe response outside the recognized cases. |
| `4` | Recipient and probe both accepted: possible catch-all domain. |
| `5` | Temporary DNS, connection, or SMTP failure: retry may help. |
| `6` | Other resolver, protocol, or SMTP command failure. |

The [usage guide](docs/usage.md#exit-statuses) explains the exact response rules
and how to capture the status in a script. For inconclusive results, start with
[troubleshooting](docs/troubleshooting.md).

Validation results go to standard output; argument errors and temporary/runtime
failures go to standard error. Before v0.1.0, these codes were revised to separate
usage errors from temporary failures; see the [migration notes](docs/usage.md#changes-before-v010).

## Documentation

Browse the [documentation index](docs/README.md), or go directly to:

- [Installation](docs/installation.md): requirements and local installation.
- [Usage](docs/usage.md): arguments, examples, output, and exit statuses.
- [How validation works](docs/validation.md): DNS resolution, SMTP sequence, and limitations.
- [Troubleshooting](docs/troubleshooting.md): common errors and next steps.
- [Development](docs/development.md): source layout, tests, and contribution guidance.

## Development

```sh
uv sync --locked
uv run pytest
uv run pytest --cov --cov-report=term-missing
```

Tests mock DNS and SMTP; they do not contact public mail servers. GitHub Actions
is configured to run the suite on Python 3.13 and 3.14.

## License

Released under the [MIT License](LICENSE).
