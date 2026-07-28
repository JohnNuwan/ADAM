#!/usr/bin/env python3
"""CTF Challenge: Network - PCAP Analysis
A network capture contains a hidden flag in HTTP traffic.
Use tcpdump or tshark to analyze the PCAP file.

Create a fake PCAP with a flag:
"""
import subprocess
print("Challenge: Network Analysis")
print("Goal: Find the flag in network traffic")
print("Hint: Use tcpdump -r capture.pcap | grep -i flag")
