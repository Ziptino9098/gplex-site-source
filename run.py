#!/usr/bin/env python3
"""Run Gplex+ on its own: a small threaded web server around plus.App.

    python3 run.py                         http://localhost:8080/, data in ./data
    python3 run.py --port 80 --https-port 443 --cert fullchain.pem --key privkey.pem

On the first start, with no members yet, it prints a link for the first account (also saved in
<data>/plus/first-invite.txt); that account is the admin. Python's standard library only.
"""
import argparse
import os
import socketserver
import ssl
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import plus

APP = None


class Handler(BaseHTTPRequestHandler):
    server_version = "GplexPlus"
    sys_version = ""
    timeout = 30

    def do_GET(self):
        APP.handle(self, "GET")

    def do_HEAD(self):
        APP.handle(self, "HEAD")

    def do_POST(self):
        APP.handle(self, "POST")

    def log_message(self, fmt, *args):
        sys.stdout.write("%s - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))
        sys.stdout.flush()


class Server(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class TLSServer(Server):
    """HTTPS. (The class name matters: plus.Request treats requests from a "TLSServer" as secure.)"""

    def __init__(self, addr, handler, cert, key):
        Server.__init__(self, addr, handler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cert, key)
        # the handshake happens in the request's own thread, so a slow client can't hold up the others
        self.socket = ctx.wrap_socket(self.socket, server_side=True, do_handshake_on_connect=False)


def main():
    global APP
    ap = argparse.ArgumentParser(description="Run Gplex+")
    ap.add_argument("--host", default="0.0.0.0", help="address to listen on (default: every interface)")
    ap.add_argument("--port", type=int, default=8080, help="HTTP port (default 8080)")
    ap.add_argument("--https-port", type=int, default=0, help="also serve HTTPS on this port; plain HTTP then redirects to it")
    ap.add_argument("--cert", help="certificate chain (PEM) for HTTPS")
    ap.add_argument("--key", help="private key (PEM) for HTTPS")
    ap.add_argument("--data-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
                    help="where the database and keys are kept (default ./data)")
    ap.add_argument("--contact", default=os.environ.get("GPLEX_PLUS_CONTACT", ""),
                    help="email shown on the terms and privacy pages (or set GPLEX_PLUS_CONTACT)")
    a = ap.parse_args()
    os.makedirs(a.data_dir, exist_ok=True)
    plus.CONTACT = a.contact
    APP = plus.App(a.data_dir, log=lambda m: (sys.stdout.write(m + "\n"), sys.stdout.flush()))
    httpd = Server((a.host, a.port), Handler)
    print("Gplex+ on http://localhost:%d/  (data in %s)" % (a.port, a.data_dir))
    if a.https_port:
        if not (a.cert and a.key):
            raise SystemExit("--https-port needs --cert and --key")
        httpsd = TLSServer((a.host, a.https_port), Handler, a.cert, a.key)
        plus.HTTPS_PORT = a.https_port
        threading.Thread(target=httpsd.serve_forever, daemon=True).start()
        print("and on https://localhost:%d/" % a.https_port)
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
