# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Addison Kline

import argparse
import base64
import random
import smtplib
from sys import exit
from time import sleep

import dns.resolver
from validators import email
from validators.utils import ValidationError


def find_mail_exchangers(
    domain: str,
) -> dns.resolver.Answer:
    """
    Attempt to find the mail exchangers for the given domain.
    If the domain has no MX records, fall back to A/AAAA records.
    """

    answers = dns.resolver.resolve(domain, "MX")
    mx_preferred = min(answers, key=lambda record: record.preference)
    hostname_preferred = str(mx_preferred.exchange).rstrip(".")
    if hostname_preferred == "":
        raise ValueError(f"the domain {domain} does not accept email")

    if len(answers) == 0:
        answers_fallback = dns.resolver.resolve(domain, "A/AAAA")
        return answers_fallback

    return sorted(answers, key=lambda mx: mx.preference)


def connect_to_exchanger(
    hostname: str,
) -> smtplib.SMTP | None:
    """
    Attempt an SMTP connection to the exchanger hostname.
    """
    try:
        return smtplib.SMTP(hostname, port=25, timeout=5.0)
    except (OSError, smtplib.SMTPException):
        return None


def verify_email(
    recipient: str,
    sender: str,
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

        smtp = connect_to_exchanger(hostname)

        if smtp is None:
            # print(f"unreachable: {hostname}")
            continue

        try:
            # print(f"connected: {hostname}")
            smtp.ehlo()

            # check provided address
            # Present the envelope sender
            sender_code, _ = smtp.mail(sender)
            if sender_code != 250:
                raise RuntimeError("sender rejected")
            # Ask whether this recipient is accepted
            real_code, real_message = smtp.rcpt(recipient)

            smtp.rset()

            # generate fake address and check that too
            fake_recipient = generate_invalid_address(recipient)
            smtp.mail(sender)
            fake_code, fake_message = smtp.rcpt(fake_recipient)

            return real_code, real_message, fake_code, fake_message
            break
        finally:
            smtp.close()
    else:
        print("no reachable mail exchangers")
        exit(5)


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
    real_code, real_message, fake_code, fake_message = verify_email(recipient, sender)

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
            print(f"got SMTP code {real_code}")
            if args.verbose:
                print(real_message)
            exit(3) 
    else:
        print(f"address validation failed for {recipient}: got SMTP code {real_code}")
        if args.verbose:
            print(real_message)
        exit(3)