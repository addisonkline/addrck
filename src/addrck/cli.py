# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Addison Kline

import argparse
import base64
import random
import smtplib
from time import sleep

import dns.resolver
from validators import email
from validators.utils import ValidationError


def verify_email(
    recipient: str,
    sender: str,
) -> tuple[int, bytes]:
    """
    Process for validating an individual email via SMTP.
    """
    # the recipient address has already been validated
    # so we can just do this
    domain = recipient.rsplit("@", 1)[1]

    # Find the domain's mail exchangers
    answers = dns.resolver.resolve(domain, "MX")
    mx = min(answers, key=lambda r: r.preference)
    hostname = str(mx.exchange).rstrip(".")

    # Connect to the receiving SMTP server
    with smtplib.SMTP(hostname, 25, timeout=10) as smtp:
        smtp.ehlo()

        # Present the envelope sender
        sender_code, _ = smtp.mail(sender)
        if sender_code != 250:
            raise RuntimeError("Sender rejected")

        # Ask whether this recipient is accepted
        code, message = smtp.rcpt(recipient)

        # QUIT is handled by context manager
        return code, message


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

    args = parser.parse_args()

    # validate sender and recipient addresses
    sender = verify_email_syntax(args.sender)
    recipient = verify_email_syntax(args.recipient)

    # check the recipient directly
    code, message = verify_email(recipient=recipient, sender=sender)
    if code != 250:
        print(f"address verification failed: SMTP code {code}")
        if args.verbose:
            print(message)
        return

    sleep(2)

    # now check to see if an invalid address is also accepted
    recipient_invalid = generate_invalid_address(recipient)
    code_invalid, message_invalid = verify_email(recipient=recipient_invalid, sender=sender)
    if code_invalid == 250:
        print("the recipient domain might accept all mailboxes")
        if args.verbose:
            print(message_invalid)
        return

    print(f"address verification passed: {recipient}")
    if args.verbose:
        print(message)