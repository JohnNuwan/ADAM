#!/usr/bin/env python3
"""CTF Challenge: Web - SQL Injection
A web server is vulnerable to SQL injection.
The login form at http://localhost:8080/login accepts username and password.
Try: admin OR 1=1 as username to bypass authentication.

Use sqlmap to automate: sqlmap -u http://localhost:8080/login --data="username=admin&password=test" --batch
"""
print("Challenge: SQL Injection")
print("Target: http://localhost:8080/login")
print("Goal: Bypass authentication using SQL injection")
print("Hint: Try admin OR 1=1 as username")
