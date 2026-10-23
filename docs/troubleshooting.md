# Troubleshooting

[Documentation index](README.md)

Start by confirming that `uv run addrck --help` works and that the command uses
`sender recipient` in that order. Add `--verbose` to see the SMTP response
messages available for a completed check. Verbose mode does not log every
connection step or attach server response text to runtime errors.

## Installation and arguments

| Symptom | What to check |
| --- | --- |
| `addrck: command not found` | Use `uv run addrck` from the repository, or activate the virtual environment used for pip installation. |
| Python version error during installation | Use Python 3.13 or newer. |
| Usage text and exit `2` | Supply both positional addresses, use recognized options, and give `--timeout` an integer. |
| `invalid email address: ...` | Correct the indicated sender or recipient syntax. |
| `timeout must be >= 0 seconds` | Use a positive integer such as `--timeout 10`. |
| `Non-blocking socket (timeout=0) is not supported` | Replace `--timeout 0` with a positive value; zero is unsupported by the SMTP client. |

## DNS and domain errors

| Message contains | Meaning and next step |
| --- | --- |
| `bad domain` | DNS returned NXDOMAIN. Check the recipient domain spelling and its DNS setup. |
| `does not accept email` | The preferred exchange is a null MX. Confirm the address with the intended recipient. |
| `no mail exchangers or address records` | No MX, A, or AAAA answers were available. Check the domain's DNS mail routing. |
| `DNS lookup failed` | A resolver failure prevented a result. Check local DNS connectivity and retry after resolving the failure. |

Increasing `--timeout` does not change DNS lookup timeouts.

## SMTP connection and command errors

`no reachable mail exchangers` means every attempted SMTP connection failed.
Check outbound TCP port 25 access, the local network/firewall, and whether the
remote exchangers are reachable. A larger positive timeout may help a slow
connection, but does not resolve a blocked port. The current output does not
include the underlying error for each failed connection.

`SMTP greeting rejected`, `SMTP reset rejected`, `sender rejected`, and
`sender rejected for probe` mean a required command did not return `250`.
Verify the envelope sender you supplied and the receiving server's acceptance
policy. These errors do not establish whether the recipient exists.

`SMTP exchange failed with ...` means a socket or SMTP exception interrupted an
established session. The message identifies the exchanger and underlying error.
The connection is closed and the check ends without trying another exchanger.

## Inconclusive or surprising results

- **Temporary failure (exit `2`):** if arguments were parsed successfully, the
  recipient or probe returned `4xx`. Try again later; there is no automatic retry.
- **Possible catch-all (exit `4`):** both addresses were accepted. addrck cannot
  distinguish this recipient from the generated probe using these replies.
- **Unexpected reply (exit `3`):** use verbose output to inspect the relevant SMTP
  message. A different `5xx` code is not automatically classified as nonexistent.
- **Likely valid, but later mail fails:** SMTP envelope acceptance does not
  guarantee later delivery. See [how validation works](validation.md).

If reporting an issue, include the Python and addrck versions, command options,
exit status, and relevant output. Redact addresses and server information you do
not want to share. Do not include credentials; addrck has no SMTP login option.
