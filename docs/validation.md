# How validation works

[Documentation index](README.md)

## Input and DNS

addrck first checks the sender and recipient syntax using `validators.email`,
then validates the integer timeout. It preserves the supplied addresses and
extracts the recipient domain for DNS lookup.

The DNS lookup follows these rules:

1. Query MX records and sort them by ascending preference: lower numbers first.
2. Reject the domain if the preferred MX exchange is `.` (a null MX).
3. If MX records are absent, query A, then AAAA if no A answer is available.
4. If either address lookup has an answer, use the domain itself as an implicit
   MX with preference zero. The address record is not passed to SMTP as an MX.
5. Reject a nonexistent domain or a domain with no MX, A, or AAAA answers.

A nonexistent domain, null MX, or missing mail/address records produces an
undeliverable result (exit `1`). Resolver timeouts and unavailable nameservers
produce temporary failures (exit `5`); other resolver errors use exit `6`.
An error on an A lookup does not trigger an AAAA retry; the fallback continues
only when the lookup has no answer.

## SMTP exchange

addrck connects directly to exchangers on TCP port 25, in preference order. A
connection failure advances to the next exchanger. If none can be reached, the
check fails. Exhausted connections use exit `5` if any failure was temporary,
or exit `6` if all failures were other SMTP errors.

Once connected, the exchange follows this sequence:

```text
EHLO                         require 250
MAIL FROM:<sender>           require 250
RCPT TO:<recipient>          record real reply; stop unless 250
RSET                         require 250
MAIL FROM:<sender>           require 250
RCPT TO:<random-probe>       record probe reply
close connection
```

The probe local part is URL-safe Base64 encoding of 16 random bytes. It uses the
same domain as the real recipient and is intended to be unlikely to name an
existing mailbox.

The connection is closed in a `finally` block after success or failure during the
exchange. No `DATA` command is issued, so no message body is submitted. The client
closes the socket rather than sending `QUIT`.
Socket/SMTP exceptions during close are ignored so cleanup cannot replace a
validation result or the original failure.

Once a connection succeeds, a command rejection or exchange exception ends the
check; addrck does not retry that exchange against another MX. It attempts the
probe only after the real recipient returns `250`. SMTP `4xx` replies at any
stage produce a temporary failure. A non-`4xx` failure of EHLO, RSET, or MAIL is
a runtime failure, rather than evidence about the recipient. See
[exit statuses](usage.md#exit-statuses) for the complete classification.

## What a result establishes

SMTP replies describe what the receiving server accepted at the time of the
check. A `250` for the recipient and `550` for the probe is evidence for a real
mailbox, but does not guarantee that a later message will be delivered.

A server that accepts both addresses may be a catch-all, or may defer recipient
validation until later. A `550` can also reflect server policy rather than mailbox
existence. Rate limits, temporary failures, and sender or connection policies can
prevent a useful result.

## Current scope

- Each invocation checks one recipient.
- SMTP uses port 25 with no authentication or STARTTLS; envelope addresses are
  sent over an unencrypted connection.
- EHLO must succeed; there is no fallback to HELO.
- There is no automatic retry/backoff after temporary replies.
- The timeout controls SMTP socket operations rather than the whole run.
- Results are printed as text, with process exit statuses for scripting.

For a specific failure, use the [troubleshooting guide](troubleshooting.md).
