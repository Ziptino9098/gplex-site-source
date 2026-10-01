"""Gplex+ - a small invite-only social network in the style of Google+ (2011-2013), served by the
Gplex Extended site's own server at plus.<your domain>.

Everything is Python's standard library: SQLite for the data, plain HTML forms (no JavaScript, so it
works in old browsers too). The data lives in the data folder (gplex-data/plus), so installing a new
site zip never touches it:
    gplex-data/plus/plus.db        members, posts, circles, comments, +1s, reports
    gplex-data/plus/media/         photos from before Gplex+ stopped taking pictures (never served now)
    gplex-data/plus/first-invite.txt   the link for the first (admin) account, until it is used

Gplex+ is a fan project in the spirit of Google+; it is not made by or connected with Google.
"""

import base64
import datetime
import email.parser
import email.policy
import hashlib
import hmac
import html
import ipaddress
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import urllib.parse
from http.cookies import SimpleCookie

NAME = "Gplex+"
BRAND_MAX = 30
MAX_INVITE_USES = 1000


def clean_brand(s):
    """The site name a member typed for themselves: one line of printable text, or "" for the default."""
    s = "".join(ch for ch in (s or "") if ch.isprintable())
    return " ".join(s.split())[:BRAND_MAX]
HTTPS_PORT = 0                       # set by server.py when it also serves HTTPS
CONTACT = os.environ.get("GPLEX_PLUS_CONTACT", "")   # the email shown on the terms and privacy pages
MAX_BODY = 64 * 1024                 # a request: forms of text only (Gplex+ takes no pictures)
MAX_POST = 5000
MAX_COMMENT = 2000
SESSION_DAYS = 30
DEFAULT_CIRCLES = ["Friends", "Family", "Acquaintances", "Following"]
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")
PAGE = 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL, pw TEXT NOT NULL,
    about TEXT NOT NULL DEFAULT '', avatar TEXT, cover TEXT, role TEXT NOT NULL DEFAULT 'member',
    status TEXT NOT NULL DEFAULT 'active', created INTEGER NOT NULL, invited_by INTEGER);
CREATE TABLE IF NOT EXISTS invites (
    code TEXT PRIMARY KEY, created_by INTEGER, created INTEGER NOT NULL, used_by INTEGER, used INTEGER,
    note TEXT NOT NULL DEFAULT '', admin INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS resets (
    token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created INTEGER NOT NULL, used INTEGER);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, csrf TEXT NOT NULL, created INTEGER NOT NULL,
    seen INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS circles (
    id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL, name TEXT NOT NULL, created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS circle_members (
    circle_id INTEGER NOT NULL, member_id INTEGER NOT NULL, added INTEGER NOT NULL,
    PRIMARY KEY (circle_id, member_id));
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY, author_id INTEGER NOT NULL, body TEXT NOT NULL, image TEXT,
    visibility TEXT NOT NULL, created INTEGER NOT NULL, removed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS post_circles (
    post_id INTEGER NOT NULL, circle_id INTEGER NOT NULL, PRIMARY KEY (post_id, circle_id));
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL, author_id INTEGER NOT NULL, body TEXT NOT NULL,
    created INTEGER NOT NULL, removed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS plusones (
    kind TEXT NOT NULL, target_id INTEGER NOT NULL, user_id INTEGER NOT NULL, created INTEGER NOT NULL,
    PRIMARY KEY (kind, target_id, user_id));
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, actor_id INTEGER NOT NULL, kind TEXT NOT NULL,
    post_id INTEGER, created INTEGER NOT NULL, seen INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY, reporter_id INTEGER, kind TEXT NOT NULL, target_id INTEGER NOT NULL,
    reason TEXT NOT NULL, created INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'open',
    resolved_by INTEGER, note TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS posts_author ON posts(author_id, id);
CREATE TABLE IF NOT EXISTS user_ips (
    user_id INTEGER NOT NULL, tag TEXT NOT NULL, first INTEGER NOT NULL, last INTEGER NOT NULL, PRIMARY KEY (user_id, tag));
CREATE TABLE IF NOT EXISTS ip_bans (
    tag TEXT PRIMARY KEY, user_id INTEGER, created INTEGER NOT NULL, by_id INTEGER);
CREATE INDEX IF NOT EXISTS comments_post ON comments(post_id, id);
CREATE INDEX IF NOT EXISTS circle_members_member ON circle_members(member_id);
CREATE INDEX IF NOT EXISTS notifications_user ON notifications(user_id, id);
"""


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def now():
    return int(time.time())


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ---- passwords: scrypt where Python has it, PBKDF2 otherwise ----
def hash_password(pw):
    salt = secrets.token_bytes(16)
    if hasattr(hashlib, "scrypt"):
        h = hashlib.scrypt(pw.encode("utf-8"), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
        return "scrypt$16384$8$1$%s$%s" % (base64.b64encode(salt).decode(), base64.b64encode(h).decode())
    h = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, 600000)
    return "pbkdf2$600000$%s$%s" % (base64.b64encode(salt).decode(), base64.b64encode(h).decode())


_COMMON_PW = {"password", "passw0rd", "qwerty", "qwertyuiop", "asdfgh", "asdfghjkl", "zxcvbnm", "letmein", "iloveyou", "welcome",
              "admin", "administrator", "monkey", "dragon", "football", "baseball", "sunshine", "princess", "shadow", "master",
              "trustno", "abc", "abcdef", "abcdefg", "google", "googleplus", "gplex", "gplexplus", "changeme", "secret", "login"}


def password_problem(pw, username="", name=""):
    """Why a password is too easy to guess, or None: at least 10 characters, not built on the username or
    name, not a well-known password with numbers stuck on, not one character or 1234... over and over."""
    if len(pw) < 10:
        return "Passwords need at least 10 characters."
    low = pw.lower()
    letters = re.sub(r"[^a-z]", "", low)
    for part in [username or ""] + re.split(r"\s+", name or ""):
        part = re.sub(r"[^a-z0-9]", "", part.lower())
        if len(part) >= 4 and (part in re.sub(r"[^a-z0-9]", "", low) or (len(re.sub(r"[^a-z]", "", part)) >= 4 and re.sub(r"[^a-z]", "", part) in letters)):
            return "Passwords can't contain your username or name. Anyone can see those."
    if letters in _COMMON_PW or not letters and len(set(low)) <= 3 or len(set(low)) <= 2 or low in "01234567890123456789" or low in "abcdefghijklmnopqrstuvwxyz":
        return "That password is one people guess first. Please pick something less common."
    return None


def check_password(pw, stored):
    try:
        parts = stored.split("$")
        if parts[0] == "scrypt":
            n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
            salt, want = base64.b64decode(parts[4]), base64.b64decode(parts[5])
            got = hashlib.scrypt(pw.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=len(want))
        elif parts[0] == "pbkdf2":
            salt, want = base64.b64decode(parts[2]), base64.b64decode(parts[3])
            got = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, int(parts[1]))
        else:
            return False
        return hmac.compare_digest(got, want)
    except (ValueError, IndexError, TypeError):
        return False


# ---- text: escaped, links made clickable, *bold* _italic_ -strike- as on Google+ ----
URL_RE = re.compile(r"(https?://[^\s<>\"']+)")


def render_text(s):
    t = esc(s)
    t = URL_RE.sub(lambda m: '<a href="%s" rel="nofollow noopener noreferrer" target="_blank">%s</a>' % (
        m.group(1), m.group(1)), t)
    t = re.sub(r"(^|[\s(])\*([^*\n<>]+)\*(?=$|[\s.,!?)])", r"\1<b>\2</b>", t)
    t = re.sub(r"(^|[\s(])_([^_\n<>]+)_(?=$|[\s.,!?)])", r"\1<i>\2</i>", t)
    t = re.sub(r"(^|[\s(])-([^\-\n<>]+)-(?=$|[\s.,!?)])", r"\1<s>\2</s>", t)
    return t.replace("\r\n", "\n").replace("\n", "<br>")


def when(ts):
    d = datetime.datetime.fromtimestamp(ts)
    today = datetime.datetime.now()
    hm = d.strftime("%I:%M %p").lstrip("0")
    if d.date() == today.date():
        return hm
    if d.year == today.year:
        return d.strftime("%b %d").replace(" 0", " ")
    return d.strftime("%b %d, %Y").replace(" 0", " ")


class Store(object):
    """The SQLite database (one connection per server thread)."""

    def __init__(self, folder):
        self.folder = folder
        self.media = os.path.join(folder, "media")
        os.makedirs(self.media, exist_ok=True)
        self.path = os.path.join(folder, "plus.db")
        self.local = threading.local()
        self.lock = threading.Lock()
        db = self.db()
        db.executescript(SCHEMA)
        if "ua" not in [r[1] for r in db.execute("PRAGMA table_info(sessions)")]:
            db.execute("ALTER TABLE sessions ADD COLUMN ua TEXT NOT NULL DEFAULT ''")
        # (added later) the name each member chose for the site, shown in place of "Gplex+"
        ucols = [r[1] for r in db.execute("PRAGMA table_info(users)")]
        if "pw_weak" not in ucols:
            db.execute("ALTER TABLE users ADD COLUMN pw_weak INTEGER NOT NULL DEFAULT 0")
        if "brand" not in ucols:
            db.execute("ALTER TABLE users ADD COLUMN brand TEXT NOT NULL DEFAULT ''")
        # (added later) which invite a member joined with (its note), for the admin's member list
        if "joined_via" not in ucols:
            db.execute("ALTER TABLE users ADD COLUMN joined_via TEXT NOT NULL DEFAULT ''")
        # (added later) invites that several people can use: an invite stays open until uses reaches max_uses
        icols = [r[1] for r in db.execute("PRAGMA table_info(invites)")]
        if "max_uses" not in icols:
            db.execute("ALTER TABLE invites ADD COLUMN max_uses INTEGER NOT NULL DEFAULT 1")
        if "uses" not in icols:
            db.execute("ALTER TABLE invites ADD COLUMN uses INTEGER NOT NULL DEFAULT 0")
        db.commit()

    def db(self):
        c = getattr(self.local, "c", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=15)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA foreign_keys=ON")
            self.local.c = c
        return c

    def q(self, sql, args=()):
        return self.db().execute(sql, args).fetchall()

    def one(self, sql, args=()):
        return self.db().execute(sql, args).fetchone()

    def run(self, sql, args=()):
        with self.lock:
            db = self.db()
            cur = db.execute(sql, args)
            db.commit()
            return cur.lastrowid

    def delete_image(self, name):
        # (photos from before Gplex+ stopped taking pictures go when their post or account is deleted)
        if name and re.match(r"^[0-9a-f]{32}\.(jpg|png|gif|webp)$", name):
            try:
                os.remove(os.path.join(self.media, name))
            except OSError:
                pass


class Reply(object):
    def __init__(self, code=200, body="", ctype="text/html; charset=utf-8"):
        self.code = code
        self.body = body
        self.ctype = ctype
        self.headers = []

    @staticmethod
    def redirect(to):
        r = Reply(302, "")
        r.headers.append(("Location", to))
        return r


class Request(object):
    """One request: its path, form, files, cookies, the member signed in and the CSRF token."""

    def __init__(self, app, handler, method):
        self.app = app
        self.h = handler
        self.method = method
        raw = handler.path.split("#", 1)[0]
        self.path, _, qs = raw.partition("?")
        self.path = re.sub(r"/{2,}", "/", self.path) or "/"
        if self.path != "/" and self.path.endswith("/"):
            self.path = self.path.rstrip("/")
        self.query = {k: v[0] for k, v in urllib.parse.parse_qs(qs).items()}
        self.form = {}
        self.files = {}
        self.cookies = SimpleCookie()
        try:
            self.cookies.load(handler.headers.get("Cookie", ""))
        except Exception:
            pass
        self.secure = handler.server.__class__.__name__ == "TLSServer"
        self.set_cookies = []
        self.user = None
        self.session = None
        self.too_big = False

    def cookie(self, name):
        m = self.cookies.get(name)
        return m.value if m else None

    def read_body(self):
        try:
            n = int(self.h.headers.get("Content-Length", "0") or 0)
        except ValueError:
            n = 0
        if n > MAX_BODY:
            self.too_big = True
            return
        data = self.h.rfile.read(n) if n > 0 else b""
        ctype = self.h.headers.get("Content-Type", "")
        if ctype.startswith("multipart/form-data"):
            msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
                b"Content-Type: " + ctype.encode("latin-1") + b"\r\n\r\n" + data)
            if msg.is_multipart():
                for part in msg.iter_parts():
                    name = part.get_param("name", header="content-disposition")
                    if not name:
                        continue
                    payload = part.get_payload(decode=True) or b""
                    if part.get_filename() is not None:
                        continue                # Gplex+ takes no files
                    elif name.endswith("[]"):
                        self.form.setdefault(name, []).append(payload.decode("utf-8", "replace"))
                    else:
                        self.form[name] = payload.decode("utf-8", "replace")
        else:
            for k, v in urllib.parse.parse_qs(data.decode("utf-8", "replace"), keep_blank_values=True).items():
                self.form[k] = v[0]
                if k.endswith("[]"):
                    self.form[k] = v

    def multi(self, name):
        v = self.form.get(name + "[]", [])
        return v if isinstance(v, list) else [v]


class App(object):
    def __init__(self, data_dir, log=print):
        self.store = Store(os.path.join(data_dir, "plus"))
        self.fails = {}
        self.fail_lock = threading.Lock()
        self.log = log
        self.ipkey = self.load_ipkey()
        self.first_invite()

    # ---- IP addresses: kept only as a keyed hash ("tag"), for permanent IP bans ----
    def load_ipkey(self):
        path = os.path.join(self.store.folder, "ip-key")
        try:
            with open(path, "rb") as f:
                k = f.read()
            if len(k) >= 32:
                return k
        except OSError:
            pass
        k = secrets.token_bytes(32)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(k)
        return k

    @staticmethod
    def ip_of(req):
        return (req.h.client_address[0] or "") if req.h.client_address else ""

    @staticmethod
    def ip_public(ip):
        """Private, loopback and link-local addresses (your own network) are never recorded or banned."""
        try:
            a = ipaddress.ip_address(ip)
            if a.version == 6 and a.ipv4_mapped:
                a = a.ipv4_mapped
            return not (a.is_private or a.is_loopback or a.is_link_local or a.is_reserved or a.is_multicast or a.is_unspecified)
        except ValueError:
            return False

    def ip_tag(self, ip):
        try:
            a = ipaddress.ip_address(ip)
            if a.version == 6 and a.ipv4_mapped:
                a = a.ipv4_mapped
            # an IPv6 user changes addresses within their /64, so the /64 is one "address"
            key = str(a) if a.version == 4 else str(ipaddress.ip_network(str(a) + "/64", strict=False).network_address) + "/64"
        except ValueError:
            return None
        return hmac.new(self.ipkey, key.encode(), hashlib.sha256).hexdigest()[:32]

    def note_ip(self, req, user_id):
        ip = self.ip_of(req)
        if not self.ip_public(ip):
            return
        tag = self.ip_tag(ip)
        if tag:
            t = now()
            self.store.run("UPDATE user_ips SET last=? WHERE user_id=? AND tag=?", (t, user_id, tag))
            self.store.run("INSERT OR IGNORE INTO user_ips (user_id, tag, first, last) VALUES (?, ?, ?, ?)", (user_id, tag, t, t))
            self.store.run("DELETE FROM user_ips WHERE last<?", (t - 180 * 86400,))

    def ip_banned(self, req):
        ip = self.ip_of(req)
        if not self.ip_public(ip):
            return False
        tag = self.ip_tag(ip)
        return bool(tag and self.store.one("SELECT 1 FROM ip_bans WHERE tag=?", (tag,)))

    # ---- the first (admin) account ----
    def first_invite(self):
        s = self.store
        if s.one("SELECT 1 FROM users LIMIT 1"):
            p = os.path.join(s.folder, "first-invite.txt")
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
            return
        row = s.one("SELECT code FROM invites WHERE admin=1 AND used_by IS NULL")
        code = row["code"] if row else None
        if not code:
            code = secrets.token_urlsafe(12)
            s.run("INSERT INTO invites (code, created, note, admin) VALUES (?, ?, 'first account', 1)", (code, now()))
        with open(os.path.join(s.folder, "first-invite.txt"), "w") as f:
            f.write("Open this to make the first Gplex+ account (it becomes the admin):\n"
                    "https://<your Gplex+ address>/join?invite=%s\n" % code)
        self.log("Gplex+: no members yet. Make the first (admin) account at /join?invite=%s on your Gplex+ address"
                 " (also in %s)" % (code, os.path.join(s.folder, "first-invite.txt")))

    # ---- sessions and CSRF ----
    def load_user(self, req):
        tok = req.cookie("gpsid")
        if not tok:
            return
        row = self.store.one("SELECT * FROM sessions WHERE token=?", (sha(tok),))
        if not row or row["created"] < now() - SESSION_DAYS * 86400:
            return
        u = self.store.one("SELECT * FROM users WHERE id=?", (row["user_id"],))
        if not u or u["status"] != "active":
            return
        req.session = row
        req.user = u
        if row["seen"] < now() - 300:
            self.store.run("UPDATE sessions SET seen=? WHERE token=?", (now(), row["token"]))
            self.note_ip(req, u["id"])

    def csrf(self, req):
        if req.session:
            return req.session["csrf"]
        tok = req.cookie("gpcsrf")
        if not tok or not re.match(r"^[A-Za-z0-9_-]{20,64}$", tok):
            tok = secrets.token_urlsafe(24)
            req.set_cookies.append(self.cookie_header(req, "gpcsrf", tok, 86400))
            req.cookies["gpcsrf"] = tok
        return tok

    def csrf_ok(self, req):
        sent = req.form.get("csrf", "")
        want = req.session["csrf"] if req.session else (req.cookie("gpcsrf") or "")
        if not want or not hmac.compare_digest(sent, want):
            return False
        # and the form came from this site, where the browser says so
        origin = req.h.headers.get("Origin") or req.h.headers.get("Referer") or ""
        host = (req.h.headers.get("Host") or "").lower()
        if origin and host:
            o = urllib.parse.urlparse(origin)
            if o.netloc and o.netloc.lower() != host:
                return False
        return True

    def cookie_header(self, req, name, value, max_age):
        c = "%s=%s; Path=/; Max-Age=%d; HttpOnly; SameSite=Lax" % (name, value, max_age)
        if req.secure:
            c += "; Secure"
        return c

    def start_session(self, req, user_id):
        tok = secrets.token_urlsafe(32)
        self.store.run("INSERT INTO sessions (token, user_id, csrf, created, seen, ua) VALUES (?, ?, ?, ?, ?, ?)",
                       (sha(tok), user_id, secrets.token_urlsafe(24), now(), now(), (req.h.headers.get("User-Agent") or "")[:300]))
        req.set_cookies.append(self.cookie_header(req, "gpsid", tok, SESSION_DAYS * 86400))
        self.note_ip(req, user_id)

    def limited(self, key):
        """Too many wrong passwords lately: 5 an hour for one account, 20 an hour from one network."""
        with self.fail_lock:
            t = now()
            lst = [x for x in self.fails.get(key, []) if x > t - 3600]
            self.fails[key] = lst
            return len(lst) >= (5 if key.startswith("u:") else 20)

    def failed(self, key):
        with self.fail_lock:
            self.fails.setdefault(key, []).append(now())

    # ---- dispatch ----
    def handle(self, handler, method):
        req = Request(self, handler, method)
        # with HTTPS running, Gplex+ is only used over it: a sign-in cookie or password sent over plain
        # HTTP could be read (and the account used) by anyone on the same network
        if not req.secure and HTTPS_PORT:
            host = (handler.headers.get("Host") or "").split(":", 1)[0]
            if host:
                port = "" if HTTPS_PORT == 443 else ":%d" % HTTPS_PORT
                raw = handler.path if handler.path.startswith("/") else "/"
                rep = Reply(301, "", "text/plain; charset=utf-8")
                rep.headers.append(("Location", "https://%s%s%s" % (host, port, raw)))
                return self.send(handler, req, rep, head=(method == "HEAD"))
        try:
            if method == "POST":
                req.read_body()
            self.load_user(req)
            # a banned network: only staff accounts get in; the rules, terms and privacy pages stay readable
            banned_ip = False
            if self.ip_banned(req) and not (req.user and req.user["role"] in ("admin", "mod")):
                banned_ip = True
                if req.user:
                    self.store.run("DELETE FROM sessions WHERE token=?", (req.session["token"],))
                    req.user = req.session = None
            if banned_ip and not (req.path in ("/rules", "/terms", "/privacy", "/about") or req.path == "/signin"):
                rep = self.page(req, "Not available", '<div class="welcome"><div class="card"><h2>Gplex+ isn\'t available here</h2>'
                                '<p>This network has been banned from Gplex+ for breaking the <a href="/rules">community rules</a>.</p></div></div>',
                                code=403, bare=True)
            elif req.too_big:
                rep = self.page(req, "Too big", '<div class="card"><h2>That was too much</h2><p>Posts and forms are text only, and that was more than Gplex+ takes.</p></div>', code=413)
            elif method == "POST":
                if not self.csrf_ok(req):
                    rep = self.page(req, "Try again", '<div class="card"><h2>Something went wrong</h2><p>The page was open too long or came from somewhere else. Go back, reload it and try again.</p></div>', code=403)
                else:
                    rep = self.route_post(req)
            else:
                rep = self.route_get(req)
        except Exception as e:  # one bad request must not take the site down
            self.log("Gplex+: error on %s %s: %s: %s" % (method, req.path, e.__class__.__name__, e))
            rep = self.page(req, "Error", '<div class="card"><h2>Something went wrong</h2><p>Please try again in a moment.</p></div>', code=500)
        self.send(handler, req, rep, head=(method == "HEAD"))

    def send(self, handler, req, rep, head=False):
        body = rep.body.encode("utf-8") if isinstance(rep.body, str) else rep.body
        handler.send_response(rep.code)
        handler.send_header("Content-Type", rep.ctype)
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Connection", "close")
        handler.send_header("X-Frame-Options", "DENY")
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Referrer-Policy", "same-origin")
        if rep.ctype.startswith("text/html"):
            handler.send_header("Content-Security-Policy",
                                "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                                "font-src 'self' https://fonts.gstatic.com; "
                                "script-src 'none'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
                                "form-action 'self'")
            handler.send_header("Cache-Control", "no-store")
        for k, v in rep.headers:
            handler.send_header(k, v)
        for c in req.set_cookies:
            handler.send_header("Set-Cookie", c)
        handler.end_headers()
        if not head:
            handler.wfile.write(body)


# the pages (plus_views.py) become App's methods
import plus_views as _views  # noqa: E402
for _n in dir(_views):
    if _n.startswith(("view_", "do_", "route_")) or _n in ("page", "signin_form"):
        setattr(App, _n, getattr(_views, _n))
