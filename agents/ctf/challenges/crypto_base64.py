#!/usr/bin/env python3
"""CTF Challenge: Crypto - Base64
Decode the following base64 string to find the flag:
Q1RGezRoZV9iNHMzNjRfNzBfZDNjMGQzNX0=

Submit the decoded flag to complete the challenge.
"""
import base64

encoded = "Q1RGezRoZV9iNHMzNjRfNzBfZDNjMGQzNX0="
print(f"Decode this: {encoded}")
print(f"Flag: {base64.b64decode(encoded).decode()}")
