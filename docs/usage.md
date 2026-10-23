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

Use a positive timeout. Zero and negative values are rejected before any DNS or
SMTP activity, with exit `2`. Zero does not mean unlimited time.

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

Exit statuses distinguish validation outcomes from problems running the check.
The probe is a randomly generated address on the recipient's domain; it is only
checked after the real recipient returns `250`.

| Status | Condition | Interpretation |
| --- | --- | --- |
| `0` | Recipient `250`, probe `550`. | Likely valid recipient. |
| `1` | Recipient `550`; or recipient domain is nonexistent, has a null MX, or has no MX/A/AAAA records. | Undeliverable recipient/domain. |
| `2` | Missing/extra arguments, unknown options, invalid address syntax, or a timeout that is not a positive integer. | Fix the invocation before retrying. |
| `3` | Any other recipient reply, or recipient `250` and an unrecognized probe reply. | Unclassified SMTP response. |
| `4` | Recipient `250`, probe `250`. | Possible catch-all domain; mailbox existence is uncertain. |
| `5` | DNS timeout or unavailable nameservers; connection/socket failure; disconnect; or SMTP `4xx` at any stage. | Temporary failure; a later retry may help. |
| `6` | Other DNS errors, SMTP protocol exceptions, or non-`4xx` failure of a required greeting/EHLO/RSET/MAIL command. | Check could not complete; inspect the error. |

`--help` also exits with `0`, without checking an address. Otherwise, only the
likely-valid outcome exits with `0`. A sender rejection never marks the recipient
undeliverable: SMTP `4xx` exits with `5`, and other sender rejections exit with `6`.

The classifier specifically recognizes `250` and `550`; it does not treat every
`2xx` reply as success or every `5xx` reply as a nonexistent mailbox. For example,
a recipient response of `554` exits with `3`.

After a real recipient reply other than `250`, the connection is closed without
RSET or a probe. A subsequent cleanup error cannot replace that result. If the
recipient was accepted but the probe transaction fails, the result is a temporary
or runtime failure, rather than a likely-valid result.

Connections are tried in MX order. A failed connection can be followed by a
successful backup, in which case the completed exchange determines the status.
If every connection fails, exit `5` when any attempt had a transport failure or
`4xx` reply; exit `6` when all failures were non-temporary SMTP errors. A failure
after a connection succeeds ends the check without trying another MX.

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
    1) echo "Recipient or domain is undeliverable" ;;
    2) echo "Fix the command arguments" ;;
    3|4) echo "Mailbox existence is uncertain" ;;
    5) echo "Temporary failure; retry later" ;;
    6) echo "Check failed; inspect the reported error" ;;
    *) echo "Unexpected process status: $status" ;;
esac
```

Validation outcomes (`0`, `1`, `3`, `4`) and their verbose responses go to standard
output. Usage errors (`2`) and temporary/runtime failures (`5`, `6`) go to standard
error, including verbose responses for temporary failures. Output is human-readable;
there is no JSON mode. The statuses above describe addrck after it starts; an
environment or installation failure in uv can have its own status.
