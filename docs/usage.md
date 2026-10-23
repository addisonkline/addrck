# Usage

[Documentation index](README.md)

## Command reference

```text
addrck [-h] [-v] [-t TIMEOUT] sender recipient
```

With the uv installation, use `uv run addrck` in place of `addrck`.

| Argument or option | Meaning | Default |
| --- | --- | --- |
| `sender` | Envelope sender presented with SMTP `MAIL FROM`. | Required |
| `recipient` | Email address to check with SMTP `RCPT TO`. | Required |
| `-h`, `--help` | Print help and exit without a network check. | Off |
| `-v`, `--verbose` | Include SMTP response messages used to explain the result. | Off |
| `-t TIMEOUT`, `--timeout TIMEOUT` | Integer SMTP socket timeout, in seconds. | `5` |

Both addresses must pass syntax validation. The sender is not independently
checked for mailbox existence; it is supplied to the receiving server during
both the recipient and probe transactions.

Use a positive timeout. Negative values are rejected during input validation.
Zero passes that validation, but Python's SMTP client rejects a zero socket
timeout when a connection is attempted. Zero does not mean unlimited time.

The timeout is passed to each SMTP connection and its socket operations. It is
not a deadline for the complete check and does not configure DNS resolver
timeouts. Multiple exchanger attempts and SMTP commands can increase total time.

## Examples

Replace these example addresses with the sender and recipient you intend to use.
Each check contacts the recipient domain's mail infrastructure.

```sh
uv run addrck sender@example.org person@example.com
uv run addrck -v sender@example.org person@example.com
uv run addrck -t 10 sender@example.org person@example.com
```

An illustrative successful result is:

```text
the address person@example.com is likely valid
```

Verbose mode adds the relevant SMTP response messages. These are printed as
Python byte strings, such as `b'mailbox accepted'`. Verbose mode is not a complete
DNS or SMTP connection trace.

## Exit statuses

These classifications apply after the SMTP exchange completes. The probe is a
randomly generated address on the recipient's domain.

| Status | Condition | Interpretation |
| --- | --- | --- |
| `0` | Recipient `250`, probe `550`. | Likely valid recipient. |
| `1` | Recipient `550`, regardless of probe reply. | Likely nonexistent recipient. |
| `2` | Recipient `400`–`499`, or recipient `250` and probe `400`–`499`. | Temporary failure; try again later. |
| `3` | Any other recipient reply, or recipient `250` and an unrecognized probe reply. | Unclassified SMTP response. |
| `4` | Recipient `250`, probe `250`. | Possible catch-all domain; mailbox existence is uncertain. |
| `5` | Invalid address/timeout, nonexistent domain, null MX, or missing mail/address records. | Input or domain routing error. |
| `6` | DNS resolver failure, all exchangers unreachable, failed EHLO/RSET/MAIL, or an SMTP exchange exception. | Runtime failure; no reliable mailbox result. |

`--help` also exits with `0`. Missing arguments, unknown options, and noninteger
timeouts are handled by the argument parser and exit with `2`. Check the output
to distinguish argument errors from temporary SMTP failures.

The classifier specifically recognizes `250` and `550`; it does not treat every
`2xx` reply as success or every `5xx` reply as a nonexistent mailbox. For example,
a recipient response of `554` exits with `3`.

If a command fails before classification, the runtime error takes precedence.
For example, the program still attempts the probe after a real recipient `550`;
a subsequent RSET failure produces exit `6` rather than exit `1`.

## Use in a shell script

Capture the status immediately. This pattern also works when the script uses
`set -e`, because the check runs inside an `if` condition:

```sh
if uv run addrck sender@example.org person@example.com; then
    status=0
else
    status=$?
fi

case "$status" in
    0) echo "Recipient likely valid" ;;
    1) echo "Recipient likely nonexistent" ;;
    2) echo "Check arguments or retry a temporary failure" ;;
    3|4) echo "Mailbox existence is uncertain" ;;
    5|6) echo "Check failed; inspect the reported error" ;;
    *) echo "Unexpected process status: $status" ;;
esac
```

Validation results, verbose responses, and handled input/runtime errors go to
standard output. Argument-parser errors go to standard error. Output is
human-readable; there is no JSON mode. The statuses above describe addrck after
it starts; an environment or installation failure in uv can have its own status.
