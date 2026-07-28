#!/usr/bin/env python3
"""CTF Challenge: Forensics - Hidden Message
A file contains a hidden message. Use strings and grep to find the flag.
File: /tmp/ctf_forensics.txt
The flag format is: CTF{...}
"""
import os, random, string

# Generate a file with hidden flag
flag = "CTF{f0r3ns1cs_1s_fun}"
noise = "".join(random.choices(string.ascii_letters + string.digits, k=5000))
content = noise[:2500] + flag + noise[2500:]

with open("/tmp/ctf_forensics.txt", "w") as f:
    f.write(content)

print("Challenge: Forensics")
print("File: /tmp/ctf_forensics.txt")
print("Goal: Find the hidden flag (format: CTF{...})")
print("Hint: Use grep CTF /tmp/ctf_forensics.txt")
