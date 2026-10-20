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
) -> tuple[int, bytes]:
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

            # Present the envelope sender
            sender_code, _ = smtp.mail(sender)
            if sender_code != 250:
                raise RuntimeError("sender rejected")

            # Ask whether this recipient is accepted
            code, message = smtp.rcpt(recipient)

            return code, message
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
    code, message = verify_email(recipient=recipient, sender=sender)
    if code == 550:
        print(f"the address {recipient} is likely nonexistent")
        if args.verbose:
            print(message)
        exit(1)
    if 400 <= code < 499:
        print(f"inconclusive: SMTP code {code}")
        print("maybe try again later?")
        if args.verbose:
            print(message)
        exit(2)

    sleep(2)

    # now check to see if an invalid address is also accepted
    recipient_invalid = generate_invalid_address(recipient)
    code_invalid, message_invalid = verify_email(recipient=recipient_invalid, sender=sender)
    if code_invalid != 550:
        if code_invalid == 250:
            print("this domain likely accepts all addresses")
            print(f"the address {recipient} passed, but so did a likely-nonexistent address")
            if args.verbose:
                print(message_invalid)
            exit(3)
        elif 400 <= code_invalid < 499:
            print(f"inconclusive: SMTP code {code}")
            print("maybe try again later?")
            if args.verbose:
                print(message)
            exit(2)
        else:
            print(f"got unexpected SMTP code: {code}")
            if args.verbose:
                print(message)
            exit(4)

    print(f"address verification passed: {recipient}")
    if args.verbose:
        print(message)
    exit(0)