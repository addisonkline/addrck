# Troubleshooting

[Documentation index](README.md)

Start by confirming that `uv run addrck --help` works and that the command uses
`sender recipient` in that order. Add `--verbose` to see the SMTP response
messages available for a completed check. Verbose mode does not log every
connection step. SMTP command failures include the reply code and message in
their diagnostic, even without verbose mode.

## Installation and arguments

| Symptom | What to check |
| --- | --- |
| `addrck: command not found` | Use `uv run addrck` from the repository, or activate the virtual environment used for pip installation. |
| Python version error during installation | Use Python 3.13 or newer. |
| Usage text and exit `2` | Supply both positional addresses, use recognized options, and give `--timeout` a positive integer. |
| `invalid email address: ...` | Correct the indicated sender or recipient syntax. |
| `timeout must be > 0 seconds` | Use a positive integer such as `--timeout 10`; zero and negative timeouts exit with `2` before networking. |

## DNS and domain errors

| Message contains | Meaning and next step |
| --- | --- |
| `nonexistent domain` | DNS returned NXDOMAIN. Check the recipient domain spelling and its DNS setup. |
| `does not accept email` | The preferred exchange is a null MX. Confirm the address with the intended recipient. |
| `no mail exchangers or address records` | No MX, A, or AAAA answers were available. Check the domain's DNS mail routing. |
| `DNS lookup failed` | A resolver failure prevented a result. Check local DNS connectivity and retry after resolving the failure. |

Increasing `--timeout` does not change DNS lookup timeouts.
The first three domain results above use exit `1`. DNS timeouts and unavailable
nameservers use exit `5`; other resolver exceptions use exit `6`.

## SMTP connection and command errors

`no reachable mail exchangers` (exit `5`) means every attempted SMTP connection
failed and at least one failure was temporary.
Check outbound TCP port 25 access, the local network/firewall, and whether the
remote exchangers are reachable. A larger positive timeout may help a slow
connection, but does not resolve a blocked port. The current output does not
include the underlying error for each failed connection.

`no usable mail exchangers` (exit `6`) means all connection attempts failed with
non-temporary SMTP errors. The diagnostic includes the last such error.

`SMTP greeting rejected`, `SMTP reset rejected`, `sender rejected`, and
`sender rejected for probe` mean a required command did not return `250`.
Verify the envelope sender you supplied and the receiving server's acceptance
policy. SMTP `4xx` replies use exit `5`, and other command failures use exit `6`.
These errors do not establish whether the recipient exists.

`SMTP exchange failed with ...` means a socket or SMTP exception interrupted an
established session. The message identifies the exchanger and underlying error.
The connection is closed and the check ends without trying another exchanger.
Socket failures, disconnects, and SMTP `4xx` exceptions use exit `5`; other SMTP
protocol exceptions use exit `6`.

## Inconclusive or surprising results

- **Temporary failure (exit `5`):** DNS, a connection, or an SMTP operation failed
  temporarily. Try again later; there is no automatic retry after an exchange fails.
- **Undeliverable (exit `1`):** the recipient returned `550` or the domain has no
  mail routing. A `550` may reflect policy; it does not prove the mailbox is absent.
- **Possible catch-all (exit `4`):** both addresses were accepted. addrck cannot
  distinguish this recipient from the generated probe using these replies.
- **Unexpected reply (exit `3`):** use verbose output to inspect the relevant SMTP
  message. A different `5xx` code is not automatically classified as nonexistent.
- **Likely valid, but later mail fails:** SMTP envelope acceptance does not
  guarantee later delivery. See [how validation works](validation.md).

If reporting an issue, include the Python and addrck versions, command options,
exit status, and relevant output. Redact addresses and server information you do
not want to share. Do not include credentials; addrck has no SMTP login option.
