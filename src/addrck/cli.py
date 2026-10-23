# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Addison Kline

import argparse
import base64
import random
import smtplib
import sys
from contextlib import suppress
from enum import IntEnum
from sys import exit

import dns.exception
import dns.name
import dns.rdataclass
import dns.rdatatype
import dns.resolver
from dns.rdtypes.ANY.MX import MX
from validators import email
from validators.utils import ValidationError


class ExitCode(IntEnum):
    VALID = 0
    UNDELIVERABLE = 1
    USAGE_ERROR = 2
    INCONCLUSIVE = 3
    CATCH_ALL = 4
    TEMPORARY_FAILURE = 5
    RUNTIME_ERROR = 6


class UndeliverableDomain(ValueError):
    """The recipient domain has no usable mail routing."""


class TemporaryFailure(RuntimeError):
    """The check could not complete and may succeed on a later attempt."""


def _smtp_failure(context: str, code: int, message: bytes) -> RuntimeError:
    error_type = TemporaryFailure if 400 <= code < 500 else RuntimeError
    return error_type(f"{context}: got SMTP code {code}: {message!r}")


def _require_smtp_success(reply: tuple[int, bytes], context: str) -> None:
    code, message = reply
    if code != 250:
        raise _smtp_failure(context, code, message)


def find_mail_exchangers(
    domain: str,
) -> list[MX]:
    """
    Attempt to find the mail exchangers for the given domain.
    If the domain has no MX records, fall back to A/AAAA records.
    """

    try:
        try:
            answers = list(dns.resolver.resolve(domain, "MX"))
        except dns.resolver.NoAnswer:
            answers = []

        if not answers:
            # An implicit MX points to the domain itself, not an address record.
            for record_type in ("A", "AAAA"):
                try:
                    addresses = dns.resolver.resolve(domain, record_type)
                except dns.resolver.NoAnswer:
                    continue
                if addresses:
                    return [MX(
                        dns.rdataclass.IN, dns.rdatatype.MX, 0,
                        dns.name.from_text(domain),
                    )]
            raise UndeliverableDomain(f"no mail exchangers or address records for {domain}")

        answers.sort(key=lambda record: record.preference)
        if str(answers[0].exchange) == ".":
            raise UndeliverableDomain(f"the domain {domain} does not accept email")
        return answers
    except dns.resolver.NXDOMAIN as e:
        raise UndeliverableDomain(f"nonexistent domain: {domain}") from e
    except (dns.exception.Timeout, dns.resolver.NoNameservers) as e:
        raise TemporaryFailure(f"DNS lookup failed for {domain}: {e}") from e
    except dns.exception.DNSException as e:
        raise RuntimeError(f"DNS lookup failed for {domain}: {e}") from e


def connect_to_exchanger(
    hostname: str,
    timeout: int,
) -> smtplib.SMTP | None:
    """
    Attempt an SMTP connection to the exchanger hostname.
    """
    try:
        return smtplib.SMTP(hostname, port=25, timeout=float(timeout))
    except smtplib.SMTPServerDisconnected:
        return None
    except smtplib.SMTPResponseException as e:
        if 400 <= e.smtp_code < 500:
            return None
        raise _smtp_failure(f"SMTP connection failed with {hostname}", e.smtp_code, e.smtp_error) from e
    except smtplib.SMTPException as e:
        raise RuntimeError(f"SMTP connection failed with {hostname}: {e}") from e
    except OSError:
        return None


def verify_email(
    recipient: str,
    sender: str,
    timeout: int,
) -> tuple[int, bytes, int | None, bytes | None]:
    """
    Process for validating an individual email via SMTP.
    """
    # the recipient address has already been validated
    # so we can just do this
    domain = recipient.rsplit("@", 1)[1]

    # Find the domain's mail exchangers
    exchangers = find_mail_exchangers(domain)

    # Connect to the receiving SMTP server
    temporary_connection_failure = False
    last_connection_error = None
    for mx in exchangers:
        hostname = str(mx.exchange).rstrip(".")

        try:
            smtp = connect_to_exchanger(hostname, timeout)
        except RuntimeError as e:
            last_connection_error = e
            continue

        if smtp is None:
            temporary_connection_failure = True
            continue

        try:
            _require_smtp_success(smtp.ehlo(), "SMTP greeting rejected")

            # check provided address
            # Present the envelope sender
            _require_smtp_success(smtp.mail(sender), "sender rejected")
            # Ask whether this recipient is accepted
            real_code, real_message = smtp.rcpt(recipient)
            # Only an accepted recipient needs a catch-all probe. In particular,
            # a later probe failure must not replace a recipient rejection.
            if real_code != 250:
                return real_code, real_message, None, None

            _require_smtp_success(smtp.rset(), "SMTP reset rejected")

            # generate fake address and check that too
            fake_recipient = generate_invalid_address(recipient)
            _require_smtp_success(smtp.mail(sender), "sender rejected for probe")
            fake_code, fake_message = smtp.rcpt(fake_recipient)

            return real_code, real_message, fake_code, fake_message
        except smtplib.SMTPResponseException as e:
            raise _smtp_failure(f"SMTP exchange failed with {hostname}", e.smtp_code, e.smtp_error) from e
        except smtplib.SMTPServerDisconnected as e:
            raise TemporaryFailure(f"SMTP exchange failed with {hostname}: {e}") from e
        except smtplib.SMTPException as e:
            raise RuntimeError(f"SMTP exchange failed with {hostname}: {e}") from e
        except OSError as e:
            raise TemporaryFailure(f"SMTP exchange failed with {hostname}: {e}") from e
        finally:
            # Socket cleanup must not replace a reply or the original failure.
            with suppress(OSError, smtplib.SMTPException):
                smtp.close()
    else:
        if last_connection_error is not None and not temporary_connection_failure:
            raise RuntimeError(f"no usable mail exchangers: {last_connection_error}") from last_connection_error
        raise TemporaryFailure("no reachable mail exchangers")


def generate_invalid_address(
    address: str
) -> str:
    """
    Generate an invalid email address with the same domain as the one provided.
    i.e., an address that has no realistic chance of being used.
    """

    # the recipient address has already been validated
    # so we can just do this
    domain = address.rsplit("@", 1)[1]

    name = base64.urlsafe_b64encode(random.randbytes(16)).decode()
    return f"{name}@{domain}"


def verify_email_syntax(
    address: str
) -> str:
    """
    Validate an email address using validators.email.
    """

    result = email(address)
    if isinstance(result, ValidationError):
        raise ValueError(f"invalid email address: {address}") from result # noqa: TRY004

    return address


def verify_timeout(
    timeout: int
) -> int:
    """
    Ensure the provided timeout limit (in seconds) is valid.
    """

    if timeout <= 0:
        raise ValueError("timeout must be > 0 seconds")

    return timeout


def run():
    parser = argparse.ArgumentParser(
        prog="addrck",
        description="simple SMTP email address verifier",
        epilog="Copyright (c) 2026 Addison Kline"
    )
    parser.add_argument(
        "sender",
        help="the email address you plan on sending from"
    )
    parser.add_argument(
        "recipient",
        help="the recipient email address to check"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="include more detailed process output"
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=5,
        help="positive SMTP socket timeout in seconds (default: %(default)s)"
    )

    args = parser.parse_args()

    # validate sender and recipient addresses
    try:
        sender = verify_email_syntax(args.sender)
        recipient = verify_email_syntax(args.recipient)
        timeout = verify_timeout(args.timeout)
    except ValueError as e:
        parser.error(str(e))

    # check the recipient directly
    try:
        real_code, real_message, fake_code, fake_message = verify_email(recipient, sender, timeout)
    except UndeliverableDomain as e:
        print(f"the address {recipient} is undeliverable: {e}")
        exit(ExitCode.UNDELIVERABLE)
    except TemporaryFailure as e:
        print(f"temporary failure checking {recipient}: {e}", file=sys.stderr)
        exit(ExitCode.TEMPORARY_FAILURE)
    except RuntimeError as e:
        print(f"check failed: {e}", file=sys.stderr)
        exit(ExitCode.RUNTIME_ERROR)

    if real_code == 550:
        print(f"the address {recipient} is likely undeliverable (SMTP code 550)")
        if args.verbose:
            print(real_message)
        exit(ExitCode.UNDELIVERABLE)
    elif 400 <= real_code < 500:
        print(f"temporary failure checking {recipient}: got SMTP code {real_code}", file=sys.stderr)
        print("perhaps try again later?", file=sys.stderr)
        if args.verbose:
            print(real_message, file=sys.stderr)
        exit(ExitCode.TEMPORARY_FAILURE)
    elif real_code == 250:
        if fake_code == 550:
            print(f"the address {recipient} is likely valid")
            if args.verbose:
                print(real_message)
                print(fake_message)
            exit(ExitCode.VALID)
        elif fake_code == 250:
            print("this domain might accept all addresses")
            print(f"the address {recipient} passed validation, but so did a likely-nonexistent mailbox address")
            if args.verbose:
                print(real_message)
                print(fake_message)
            exit(ExitCode.CATCH_ALL)
        elif fake_code is not None and 400 <= fake_code < 500:
            print(f"temporary failure checking {recipient}: got SMTP code {fake_code} for probe address", file=sys.stderr)
            print("perhaps try again later?", file=sys.stderr)
            if args.verbose:
                print(real_message, file=sys.stderr)
                print(fake_message, file=sys.stderr)
            exit(ExitCode.TEMPORARY_FAILURE)
        else:
            print(f"got SMTP code {fake_code} for probe address")
            if args.verbose:
                print(fake_message)
            exit(ExitCode.INCONCLUSIVE)
    else:
        print(f"address validation failed for {recipient}: got SMTP code {real_code}")
        if args.verbose:
            print(real_message)
        exit(ExitCode.INCONCLUSIVE)
