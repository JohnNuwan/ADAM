#!/usr/bin/env python3
"""CTF Challenge: Reversing - Simple Algorithm
The following function encodes a flag. Reverse it to find the original flag.

Encoded: 4c5a4b5a5a5755534c4756464a564f52
This is hex-encoded. Decode it, then reverse the string.
"""
encoded = "4c5a4b5a5a5755534c4756464a564f52"
decoded = bytes.fromhex(encoded).decode()
reversed_flag = decoded[::-1]
print(f"Encoded: {encoded}")
print(f"Decoded: {decoded}")
print(f"Reversed (flag): {reversed_flag}")
