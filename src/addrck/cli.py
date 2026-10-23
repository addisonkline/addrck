# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Addison Kline

import argparse
import base64
import random
import smtplib
from sys import exit

import dns.exception
import dns.name
import dns.rdataclass
import dns.rdatatype
import dns.resolver
from dns.rdtypes.ANY.MX import MX
from validators import email
from validators.utils import ValidationError


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
            raise ValueError(f"no mail exchangers or address records for {domain}")

        answers.sort(key=lambda record: record.preference)
        if str(answers[0].exchange) == ".":
            raise ValueError(f"the domain {domain} does not accept email")
        return answers
    except dns.resolver.NXDOMAIN as e:
        raise ValueError(f"bad domain: {domain}") from e
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
    except (OSError, smtplib.SMTPException):
        return None


def verify_email(
    recipient: str,
    sender: str,
    timeout: int,
) -> tuple[int, bytes, int, bytes]:
    """
    Process for validating an individual email via SMTP.
    """
    # the recipient address has already been validated
    # so we can just do this
    domain = recipient.rsplit("@", 1)[1]

    # Find the domain's mail exchangers
    exchangers = find_mail_exchangers(domain)

    # Connect to the receiving SMTP server
    for mx in exchangers:
        hostname = str(mx.exchange).rstrip(".")

        smtp = connect_to_exchanger(hostname, timeout)

        if smtp is None:
            # print(f"unreachable: {hostname}")
            continue

        try:
            # print(f"connected: {hostname}")
            ehlo_code, _ = smtp.ehlo()
            if ehlo_code != 250:
                raise RuntimeError("SMTP greeting rejected")

            # check provided address
            # Present the envelope sender
            sender_code, _ = smtp.mail(sender)
            if sender_code != 250:
                raise RuntimeError("sender rejected")
            # Ask whether this recipient is accepted
            real_code, real_message = smtp.rcpt(recipient)

            reset_code, _ = smtp.rset()
            if reset_code != 250:
                raise RuntimeError("SMTP reset rejected")

            # generate fake address and check that too
            fake_recipient = generate_invalid_address(recipient)
            sender_code, _ = smtp.mail(sender)
            if sender_code != 250:
                raise RuntimeError("sender rejected for probe")
            fake_code, fake_message = smtp.rcpt(fake_recipient)

            return real_code, real_message, fake_code, fake_message
        except (OSError, smtplib.SMTPException) as e:
            raise RuntimeError(f"SMTP exchange failed with {hostname}: {e}") from e
        finally:
            smtp.close()
    else:
        raise RuntimeError("no reachable mail exchangers")


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

    if timeout < 0:
        raise ValueError("timeout must be >= 0 seconds")

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
        help="the number of seconds until the SMTP connection times out (default: %(default)s)"
    )

    args = parser.parse_args()

    # validate sender and recipient addresses
    try:
        sender = verify_email_syntax(args.sender)
        recipient = verify_email_syntax(args.recipient)
        timeout = verify_timeout(args.timeout)
    except ValueError as e:
        print(e)
        exit(5)


    # check the recipient directly
    try:
        real_code, real_message, fake_code, fake_message = verify_email(recipient, sender, timeout)
    except ValueError as e:
        print(f"invalid input: {e}")
        exit(5)
    except RuntimeError as e:
        print(f"unexpected runtime error: {e}")
        exit(6)

    if real_code == 550:
        print(f"the address {recipient} is likely nonexistent")
        if args.verbose:
            print(real_message)
        exit(1)
    elif 400 <= real_code < 500:
        print(f"temporary failure checking {recipient}")
        print("perhaps try again later?")
        if args.verbose:
            print(real_message)
        exit(2)
    elif real_code == 250:
        if fake_code == 550:
            print(f"the address {recipient} is likely valid")
            if args.verbose:
                print(real_message)
                print(fake_message)
            exit(0)
        elif fake_code == 250:
            print("this domain might accept all addresses")
            print(f"the address {recipient} passed validation, but so did a likely-nonexistent mailbox address")
            if args.verbose:
                print(real_message)
                print(fake_message)
            exit(4)
        elif 400 <= fake_code < 500:
            print(f"temporary failure checking {recipient}")
            print("perhaps try again later?")
            if args.verbose:
                print(real_message)
                print(fake_message)
            exit(2)
        else:
            print(f"got SMTP code {fake_code} for probe address")
            if args.verbose:
                print(fake_message)
            exit(3) 
    else:
        print(f"address validation failed for {recipient}: got SMTP code {real_code}")
        if args.verbose:
            print(real_message)
        exit(3)
