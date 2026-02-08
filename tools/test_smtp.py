#!/usr/bin/env python3
"""
Simple SMTP/connectivity diagnostic script.
Usage:
  python3 tools/test_smtp.py --host smtp.example.com --from user@example.com --to dest@example.com --user user@example.com --pass 'SecretPass123'

It will:
- Try TCP connect to ports 25, 465, 587
- If openssl available, try TLS handshake on 587 (STARTTLS) and 465 (SSL)
- Try to open an SMTP session with smtplib and report errors
"""
import socket
import argparse
import subprocess
import sys
import ssl
import smtplib

PORTS = [25, 465, 587]

parser = argparse.ArgumentParser()
parser.add_argument("--host", required=True)
parser.add_argument("--from", dest="mail_from", required=True)
parser.add_argument("--to", dest="mail_to", required=True)
parser.add_argument("--user", dest="username", default=None)
parser.add_argument("--pass", dest="password", default=None)
parser.add_argument("--timeout", dest="timeout", type=int, default=5)
parser.add_argument("--send", dest="send", action="store_true", help="Send a simple test email (uses DATA)")
args = parser.parse_args()

host = args.host
mail_from = args.mail_from
mail_to = args.mail_to
username = args.username
password = args.password
timeout = args.timeout
send_flag = args.send

print(f"Testing host: {host} (timeout={timeout}s)")

# 1) DNS resolve
try:
    addrinfo = socket.getaddrinfo(host, None)
    ips = sorted({ai[4][0] for ai in addrinfo})
    print("Resolved IPs:", ", ".join(ips))
except Exception as e:
    print("DNS resolution failed:", e)

# 2) TCP connect tests
for p in PORTS:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, p))
        print(f"TCP connect to {host}:{p} => OK")
    except Exception as e:
        print(f"TCP connect to {host}:{p} => FAILED: {e}")
    finally:
        s.close()

# 3) OpenSSL s_client tests if openssl is present
def run_openssl_starttls(port, use_ssl=False):
    cmd = ["openssl", "s_client"]
    if use_ssl:
        cmd += ["-connect", f"{host}:{port}"]
    else:
        cmd += ["-starttls", "smtp", "-connect", f"{host}:{port}"]
    try:
        out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        if out.returncode == 0:
            print(f"OpenSSL s_client ({'SSL' if use_ssl else 'STARTTLS'}) to {host}:{port} => OK")
        else:
            stderr = out.stderr.decode('utf-8', errors='ignore')
            print(f"OpenSSL s_client ({'SSL' if use_ssl else 'STARTTLS'}) to {host}:{port} => FAILED (exit {out.returncode})")
            print(stderr.splitlines()[:10])
    except FileNotFoundError:
        print("OpenSSL not found on PATH; skipping s_client tests.")
    except Exception as e:
        print(f"OpenSSL s_client to {host}:{port} => EXCEPTION: {e}")

run_openssl_starttls(587, use_ssl=False)
run_openssl_starttls(465, use_ssl=True)

# 4) Try smtplib session attempts
# Try port-specific behavior
for p in PORTS:
    print(f"\nTrying smtplib on port {p}...")
    try:
        if p == 465:
            server = smtplib.SMTP_SSL(host, p, timeout=timeout)
        else:
            server = smtplib.SMTP(host, p, timeout=timeout)
        server.set_debuglevel(1)
        # identify
        server.ehlo()
        if p == 587:
            try:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                print("STARTTLS negotiation OK")
            except Exception as e:
                print("STARTTLS failed:", e)
        # try auth if credentials provided
        if username and password:
            try:
                server.login(username, password)
                print("SMTP auth OK")
            except Exception as e:
                print("SMTP auth FAILED:", e)
        # try MAIL FROM / RCPT TO (no DATA)
        try:
            code, resp = server.mail(mail_from)
            if code not in (250, 220):
                print(f"MAIL FROM returned {code} {resp}")
            code, resp = server.rcpt(mail_to)
            print(f"RCPT TO returned {code} {resp}")
            # If requested, attempt to send a minimal email body
            if send_flag:
                try:
                    msg = f"From: {mail_from}\r\nTo: {mail_to}\r\nSubject: Thanos test email\r\n\r\nThis is a test email from Thanos."
                    server.sendmail(mail_from, [mail_to], msg)
                    print("sendmail: message sent (server accepted DATA)")
                except Exception as e:
                    print("sendmail failed:", e)
        except Exception as e:
            print("MAIL/RCPT commands failed:", e)
        try:
            server.quit()
        except Exception:
            server.close()
    except Exception as e:
        print(f"Connection attempt on port {p} failed: {e}")

print("\nFinished tests.")
