"""Gplex+ pages: the stream, posts, Circles, +1s, comments, profiles, notifications, settings, reports
and the admin tools. Every page is plain HTML with forms (no JavaScript). Methods of plus.App."""

import json
import os
import re
import secrets

import plus as P
import plus_filter

BLOCKED = "That has a word or phrase Gplex+ doesn't allow (see the community rules). Please reword it."
LINK_WAIT = 2 * 3600        # new members can't share links (web addresses) for their first two hours


def name_problem(self, name, uname=None, uid=None, staff=False):
    """Why a display name (and, when joining, a username) can't be used, or None. Names may not pass for
    another member's name or username, look-alike letters and all, and only staff names may use words
    like admin, moderator or official."""
    sk = plus_filter.skeleton(name)
    if not sk:
        return "Names need some letters or numbers."
    if not staff and (plus_filter.reserved(name) or (uname and plus_filter.reserved(uname))):
        return "That name is kept for the people who run Gplex+. Please pick another."
    mine = {sk}
    if uname:
        mine.add(plus_filter.skeleton(uname))
    for o in self.store.q("SELECT id, username, name FROM users"):
        if o["id"] == uid:
            continue
        if plus_filter.skeleton(o["name"]) in mine or plus_filter.skeleton(o["username"]) in mine:
            return "That looks too much like another member's name (@%s). Please pick another." % o["username"]
    return None


def who_html(u):
    """The author line: the name, the @username (unique, so it can't be borrowed) and a staff badge."""
    role = u.get("role") if isinstance(u, dict) else (u["role"] if "role" in u.keys() else None)
    badge = {"admin": '<span class="badge">Admin</span>', "mod": '<span class="badge mod">Moderator</span>'}.get(role, "")
    return '<a class="who" href="/u/%s">%s</a> <span class="handle">@%s</span>%s' % (esc(u["username"]), esc(u["name"]), esc(u["username"]), badge)


def link_wait(self, req, *texts):
    """The message for a new member trying to share a link, or None."""
    u = req.user
    if not u or u["role"] in ("admin", "mod"):
        return None
    left = u["created"] + LINK_WAIT - now()
    if left <= 0 or not any(plus_filter.has_link(t or "") for t in texts):
        return None
    mins = (left + 59) // 60
    when_ = "%d minute%s" % (mins, "" if mins == 1 else "s") if mins < 60 else "%d hour%s %d minutes" % (mins // 60, "" if mins // 60 == 1 else "s", mins % 60)
    return ("New members can share links once they've been on Gplex+ for 2 hours. You can share this one in about %s, "
            "or take the link out for now." % when_)
from plus import esc, now, Reply, render_text, when

CSS = """
body{margin:0;background:#e5e5e5;font:13px Arial,Helvetica,sans-serif;color:#404040}
a{color:#36c;text-decoration:none}a:hover{text-decoration:underline}
#top{background:#f5f5f5;border-bottom:1px solid #d6d6d6;height:58px}
#top table{width:1010px;margin:0 auto;height:58px}
#logo{font:bold 26px Arial,sans-serif;color:#666;letter-spacing:-1px;white-space:nowrap}#logo span{color:#dd4b39}#logo a{color:#666;text-decoration:none}
#search input.q{width:330px;height:30px;box-sizing:border-box;border:1px solid #d9d9d9;border-top-color:#c0c0c0;padding:0 8px;font-size:13px;vertical-align:middle;margin:0}
#search input.go{height:30px;box-sizing:border-box;border:1px solid #3079ed;background:#4d90fe;color:#fff;font:bold 13px Arial,sans-serif;padding:0 14px;cursor:pointer;vertical-align:middle;margin:0 0 0 2px}
.handle{color:#999;font-size:12px;font-weight:normal}
.badge{display:inline-block;margin-left:5px;padding:0 5px;border-radius:2px;background:#dd4b39;color:#fff;font:bold 10px/16px Arial,sans-serif;text-transform:uppercase;vertical-align:2px}
.badge.mod{background:#4285f4}
#me{text-align:right;white-space:nowrap}#meav{display:none}
.streamhead{padding:10px 16px}.streamhead b{font-size:16px;color:#262626}.streamhead a.on{font-weight:bold;color:#dd4b39}#me a.n{color:#404040;font-weight:bold;margin-right:10px}
.bell{display:inline-block;min-width:16px;padding:3px 6px;margin-right:12px;background:#dd4b39;color:#fff!important;font-weight:bold;text-align:center;border-radius:2px}
.bell.zero{background:#e5e5e5;color:#999!important}
#layout{width:1010px;margin:14px auto 0 auto;border-collapse:collapse}
#layout td{vertical-align:top;padding:0}
#nav{width:150px;padding-right:14px!important}
#nav a{display:block;padding:8px 10px;color:#666;font-size:14px;border-left:4px solid transparent}
#nav a.on{color:#dd4b39;font-weight:bold;border-left-color:#dd4b39;background:#f5f5f5}
#nav a:hover{text-decoration:none;color:#404040;background:#f5f5f5}
#main{width:560px}
#main.wide{width:836px}
#side{width:260px;padding-left:16px!important}
.card{background:#fff;border:1px solid #d8d8d8;border-bottom-color:#c8c8c8;border-radius:2px;padding:14px 16px;margin-bottom:12px}
.card h2{font-size:18px;font-weight:normal;color:#262626;margin:0 0 10px 0}
.card h3{font-size:14px;color:#262626;margin:0 0 8px 0}
.muted{color:#999}.small{font-size:11px}
.av{float:left;margin-right:10px}
.av img,.av span{display:block;width:46px;height:46px}
.av span{color:#fff;font:bold 22px/46px Arial,sans-serif;text-align:center}
.avs img,.avs span{width:28px;height:28px}.avs span{font-size:13px;line-height:28px}
.avl img,.avl span{width:120px;height:120px}.avl span{font-size:56px;line-height:120px}
.post .who{font-weight:bold;color:#262626}.post .meta{color:#999;font-size:11px;margin-top:2px}
.post .body{clear:both;padding-top:10px;font-size:13px;line-height:1.45;word-wrap:break-word}
.acts{margin-top:10px;padding-top:8px;border-top:1px solid #f0f0f0}
.acts form{display:inline;margin:0}
form.inl{display:inline;margin:0}
.acts *{vertical-align:middle}
.linkbtn{border:0;background:none;padding:0;margin:0;color:#36c;cursor:pointer;font:12px Arial,sans-serif;vertical-align:middle}
.linkbtn:hover{text-decoration:underline}
.linkbtn.s{font-size:11px}
.pt{overflow:hidden}
.tools{margin-top:4px;font-size:11px}.tools *{vertical-align:middle}.tools .p1{margin-right:8px}.tools a,.tools .linkbtn{margin-right:8px}
.p1{vertical-align:middle;border:1px solid #d9d9d9;background:#f8f8f8;color:#444;font:bold 11px Arial,sans-serif;padding:3px 7px;border-radius:2px;cursor:pointer}
.p1.on{background:#dd4b39;border-color:#c53727;color:#fff}
.acts .lnk{margin-left:12px;font-size:12px}
.acts .linkbtn{margin-left:12px}
.comments{background:#f6f6f6;margin:10px -16px -14px -16px;padding:8px 16px;border-top:1px solid #ececec}
.cm{padding:8px 0;border-bottom:1px solid #ececec;overflow:hidden}.cm:last-child{border-bottom:0}
.cm .txt{overflow:hidden;line-height:1.4;word-wrap:break-word}
.btn{display:inline-block;line-height:normal;text-decoration:none!important;vertical-align:middle;border:1px solid #3079ed;background:#4d90fe;color:#fff;font:bold 12px Arial,sans-serif;padding:6px 14px;border-radius:2px;cursor:pointer}
.btn.share{border-color:#2d6200;background:#3d9400}
.btn.red{border-color:#c53727;background:#dd4b39}
.btn.grey{border-color:#c6c6c6;background:#f5f5f5;color:#444}
textarea,input.t{width:96%;max-width:540px;box-sizing:border-box;border:1px solid #d9d9d9;border-top-color:#c0c0c0;padding:6px;font:13px Arial,sans-serif}
textarea{height:70px}
.share-box .aud{margin:8px 0;padding:8px;background:#f5f5f5;border:1px solid #e5e5e5}
.chip{display:inline-block;margin:2px 6px 2px 0;padding:2px 8px;border:1px solid #c6dafc;background:#e8f0fe;color:#1a57b5;border-radius:2px;font-size:12px}
.chip.pub{border-color:#b7dfb9;background:#e6f4e7;color:#2d6200}
.err{background:#f9edbe;border:1px solid #f0c36d;padding:8px 10px;margin-bottom:10px}
.ok{background:#e6f4e7;border:1px solid #b7dfb9;padding:8px 10px;margin-bottom:10px}
.person{overflow:hidden;padding:10px 0;border-bottom:1px solid #f0f0f0}.person:last-child{border-bottom:0}
.person .circ{margin-top:6px;font-size:12px}
.person .circ *,.circ *{vertical-align:middle}
.circ label{display:inline-block;margin:2px 10px 2px 0}
.bubbles{overflow:hidden}
.bubble{float:left;width:118px;height:118px;margin:0 14px 14px 0;border-radius:60px;border:2px solid #d9d9d9;background:#fafafa;text-align:center}
.bubble b{display:block;margin-top:38px;font-size:14px;color:#404040}.bubble span{color:#999;font-size:12px}
.cover{height:170px;background:#c5c5c5;margin:-14px -16px 0 -16px;overflow:hidden}
.prof{position:relative}.prof .av{position:relative;z-index:2;margin:-64px 18px 0 0;border:4px solid #fff;background:#fff}
.clr{clear:both;height:0;overflow:hidden}
.prof .pt{padding-top:10px}.prof h1{font:normal 26px Arial,sans-serif;color:#262626;margin:0 0 4px 0}
.prof .about{margin-top:10px;line-height:1.45}.prof .pacts{margin-top:12px}.prof .pacts *{vertical-align:middle}
table.list{width:100%;border-collapse:collapse}table.list td,table.list th{text-align:left;padding:6px 6px;border-bottom:1px solid #f0f0f0;vertical-align:middle}
table.list input.t{width:100%;max-width:none}
table.members td:first-child{width:150px}table.members td:nth-child(2){width:170px}table.members form{margin:2px 2px 2px 0!important}table.members .btn{padding:3px 7px!important;font-size:11px}
#foot{width:1010px;margin:18px auto 30px auto;color:#888;font-size:11px;text-align:center;line-height:1.7}
#foot a{color:#777}
.welcome{width:820px;margin:50px auto;overflow:hidden}
.welcome .pitch{float:left;width:440px;padding-top:20px}.welcome .pitch h1{font:normal 34px Arial,sans-serif;color:#262626;margin:0 0 14px 0}
.welcome .pitch p{font-size:15px;line-height:1.5;color:#555}
.welcome .box{float:right;width:300px}
"""

AV_COLORS = ["#db4437", "#4285f4", "#0f9d58", "#f4b400", "#ab47bc", "#00acc1", "#ff7043", "#9e9d24", "#5c6bc0", "#8d6e63"]


def avatar(u, size=""):
    cls = "av" + ((" av" + size) if size else "")
    # Gplex+ shows no pictures: everyone is a coloured initial
    initial = (u["name"] or u["username"] or "?").strip()[:1].upper()
    return '<a class="%s" href="/u/%s"><span style="background:%s">%s</span></a>' % (
        cls, esc(u["username"]), AV_COLORS[u["id"] % len(AV_COLORS)], esc(initial))


def hidden_csrf(self, req):
    return '<input type="hidden" name="csrf" value="%s">' % esc(self.csrf(req))


def brand(req):
    """The name the signed-in member chose for the site (Settings), or Gplex+."""
    u = req.user
    try:
        b = u["brand"] if u else ""
    except (IndexError, KeyError):
        b = ""
    return b or P.NAME


def brand_html(req):
    # marked so the Gplex Extended script can show the name its user picked (unless the member picked one here)
    return '<span class="gp-brand">%s</span>' % esc(brand(req))


def logo_html(name):
    # a trailing + is drawn red, the way the logo always was
    if len(name) > 1 and name.endswith("+"):
        return esc(name[:-1]) + "<span>+</span>"
    return esc(name)


def page(self, req, title, body, code=200, side="", nav=None, bare=False):
    u = req.user
    nm = brand(req)
    top = ""
    if u:
        unread = self.store.one("SELECT COUNT(*) AS n FROM notifications WHERE user_id=? AND seen=0", (u["id"],))["n"]
        top = ('<td id="search"><form action="/people" method="get"><input class="q" type="text" name="q" '
               'placeholder="Search for people" value="%s"> <input class="go" type="submit" value="Search"></form></td>'
               '<td id="me"><a class="bell%s" href="/notifications" title="Notifications">%d</a>'
               '<span id="meav">%s</span><a class="n" href="/u/%s">%s</a>'
               '<form action="/signout" method="post" style="display:inline">%s<input class="btn grey" type="submit" value="Sign out"></form></td>') % (
            esc(req.query.get("q", "")) if req.path == "/people" else "", "" if unread else " zero", unread,
            avatar(u, "s"), esc(u["username"]), esc(u["name"]), hidden_csrf(self, req))
    head = ('<div id="top"><table cellpadding="0" cellspacing="0"><tr><td id="logo"><a class="gp-logo" href="/">%s</a></td>%s'
            '</tr></table></div>') % (logo_html(nm), top)
    if u and u["pw_weak"] and not bare:
        body = ('<div class="err"><b>Your password is too easy to guess</b> (it uses your name, or is a common one), so someone else could '
                'sign in as you. Your account can\'t post until you <a href="/settings#password">change it</a>.</div>') + body
    if bare or not u:
        inner = body
    else:
        items = [("/", "Home", "home"), ("/u/" + u["username"], "Profile", "profile"), ("/explore", "Explore", "explore"),
                 ("/people", "People", "people"), ("/circles", "Circles", "circles"),
                 ("/notifications", "Notifications", "notifications"), ("/settings", "Settings", "settings")]
        if u["role"] == "admin":
            items.append(("/admin", "Admin", "admin"))
        elif u["role"] == "mod":
            items.append(("/admin", "Moderate", "admin"))
        navh = "".join('<a href="%s"%s>%s</a>' % (esc(h), ' class="on"' if k == nav else "", esc(t)) for h, t, k in items)
        if side:
            inner = ('<table id="layout"><tr><td id="nav">%s</td><td id="main">%s</td><td id="side">%s</td></tr></table>') % (
                navh, body, side)
        else:
            inner = ('<table id="layout"><tr><td id="nav">%s</td><td id="main" class="wide" colspan="2">%s</td></tr></table>') % (
                navh, body)
    foot = ('<div id="foot"><a href="/rules">Community rules</a> &nbsp;-&nbsp; <a href="/terms">Terms</a> &nbsp;-&nbsp; '
            '<a href="/privacy">Privacy</a> &nbsp;-&nbsp; <a href="https://gplexextended.com/">Gplex Extended</a><br>'
            'Gplex+ is a small fan-run community in the spirit of Google+. It is not made by, affiliated with or endorsed by Google.</div>')
    doc = ('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">\n'
           '<html%s><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
           '<meta name="viewport" content="width=1040"><title>%s</title><style type="text/css">%s</style></head>'
           '<body class="%s">%s%s%s</body></html>') % (
        ' data-gp-brand="custom"' if nm != P.NAME else "", esc(title + " - " + nm if title != P.NAME else nm), CSS,
        ("nav-" + nav if nav else "nav-none") + (" in" if u else " out") + (" bare" if bare or not u else ""), head, inner, foot)
    return Reply(code, doc)


# ---- ranks: member, mod (moderator), admin ----
# Moderators answer reports and suspend members; they can't act on other moderators or admins.
# Admins can do everything, including suspending moderators and admins and changing ranks.
ROLE_NAMES = {"member": "member", "mod": "moderator", "admin": "admin"}


def is_staff(u):
    return bool(u) and u["role"] in ("admin", "mod")


def is_admin(u):
    return bool(u) and u["role"] == "admin"


def can_moderate(actor, target):
    """May actor suspend target or remove what target posted? (Never themselves.)"""
    if not actor or not target or actor["id"] == target["id"]:
        return False
    if actor["role"] == "admin":
        return True
    return actor["role"] == "mod" and target["role"] == "member"


def need_user(self, req):
    if not req.user:
        return Reply.redirect("/signin?next=" + P.urllib.parse.quote(req.path))
    return None


def get_user(self, username):
    return self.store.one("SELECT * FROM users WHERE username=? AND status='active'", ((username or "").lower(),))


def my_circles(self, uid):
    return self.store.q("SELECT c.*, (SELECT COUNT(*) FROM circle_members m JOIN users x ON x.id=m.member_id AND x.status='active' "
                        "WHERE m.circle_id=c.id) AS n FROM circles c WHERE owner_id=? ORDER BY id", (uid,))


VISIBLE = ("p.removed=0 AND a.status='active' AND (p.author_id=:v OR p.visibility='public' OR EXISTS("
           "SELECT 1 FROM post_circles pc JOIN circle_members cm ON cm.circle_id=pc.circle_id "
           "WHERE pc.post_id=p.id AND cm.member_id=:v))")


def query_posts(self, req, where, args, before=None):
    a = dict(args)
    a["v"] = req.user["id"]
    a["lim"] = P.PAGE + 1
    sql = ("SELECT p.*, a.username, a.name, a.avatar, a.role, a.id AS uid FROM posts p JOIN users a ON a.id=p.author_id "
           "WHERE " + VISIBLE + " AND (" + where + ")")
    if before:
        sql += " AND p.id < :before"
        a["before"] = int(before)
    sql += " ORDER BY p.id DESC LIMIT :lim"
    return self.store.q(sql, a)


def can_see(self, req, post_id):
    return self.store.one("SELECT p.*, a.username, a.name, a.avatar, a.role, a.id AS uid FROM posts p JOIN users a ON a.id=p.author_id "
                          "WHERE p.id=:id AND " + VISIBLE, {"id": post_id, "v": req.user["id"]})


def user_row(r):
    return {"id": r["uid"], "username": r["username"], "name": r["name"], "avatar": r["avatar"],
            "role": r["role"] if "role" in r.keys() else None}


def plus_button(self, req, kind, target_id, back):
    n = self.store.one("SELECT COUNT(*) AS n FROM plusones WHERE kind=? AND target_id=?", (kind, target_id))["n"]
    mine = self.store.one("SELECT 1 FROM plusones WHERE kind=? AND target_id=? AND user_id=?", (kind, target_id, req.user["id"]))
    return ('<form class="inl" action="/plus" method="post">%s<input type="hidden" name="kind" value="%s"><input type="hidden" name="id" value="%d">'
            '<input type="hidden" name="back" value="%s"><input class="p1%s" type="submit" value="+1%s" title="%s"></form>') % (
        hidden_csrf(self, req), kind, target_id, esc(back), " on" if mine else "", (" " + str(n)) if n else "",
        "Undo +1" if mine else "+1 this")


def audience(self, req, p):
    if p["visibility"] == "public":
        return "Shared publicly"
    if p["author_id"] == req.user["id"]:
        names = [r["name"] for r in self.store.q("SELECT c.name FROM post_circles pc JOIN circles c ON c.id=pc.circle_id "
                                                 "WHERE pc.post_id=? ORDER BY c.id", (p["id"],))]
        return "Shared with " + esc(", ".join(names) or "nobody")
    return "Limited"


def post_card(self, req, p, full=False, back="/"):
    u = user_row(p)
    out = ['<div class="card post" id="p%d">' % p["id"], avatar(u),
           '<div>%s' % who_html(u),
           '<div class="meta">%s - <a class="muted" href="/p/%d">%s</a></div></div>' % (audience(self, req, p), p["id"], when(p["created"]))]
    if p["body"]:
        out.append('<div class="body">%s</div>' % render_text(p["body"]))
    else:
        out.append('<div class="body"></div>')
    ncom = self.store.one("SELECT COUNT(*) AS n FROM comments WHERE post_id=? AND removed=0", (p["id"],))["n"]
    acts = [plus_button(self, req, "post", p["id"], back)]
    acts.append('<a class="lnk" href="/p/%d#comments">%s</a>' % (p["id"], "Comment" if not ncom else ("%d comment%s" % (ncom, "" if ncom == 1 else "s"))))
    if p["author_id"] == req.user["id"] or (is_staff(req.user) and can_moderate(req.user, self.store.one("SELECT * FROM users WHERE id=?", (p["author_id"],)))):
        acts.append('<form action="/p/%d/delete" method="post">%s<input class="linkbtn" type="submit" value="Delete"></form>' % (
            p["id"], hidden_csrf(self, req)))
    if p["author_id"] != req.user["id"]:
        acts.append('<a class="lnk muted" href="/report?kind=post&amp;id=%d">Report</a>' % p["id"])
    out.append('<div class="acts">%s</div>' % "".join(acts))
    if full:
        coms = self.store.q("SELECT c.*, a.username, a.name, a.avatar, a.role, a.id AS uid FROM comments c JOIN users a ON a.id=c.author_id "
                            "WHERE c.post_id=? AND c.removed=0 AND a.status='active' ORDER BY c.id", (p["id"],))
    else:
        coms = list(reversed(self.store.q("SELECT c.*, a.username, a.name, a.avatar, a.role, a.id AS uid FROM comments c JOIN users a ON a.id=c.author_id "
                                          "WHERE c.post_id=? AND c.removed=0 AND a.status='active' ORDER BY c.id DESC LIMIT 3", (p["id"],))))
    cm = []
    if not full and ncom > len(coms):
        cm.append('<div class="cm"><a href="/p/%d#comments">See all %d comments</a></div>' % (p["id"], ncom))
    for c in coms:
        cu = user_row(c)
        tools = plus_button(self, req, "comment", c["id"], back)
        if c["author_id"] == req.user["id"] or p["author_id"] == req.user["id"] or (
                is_staff(req.user) and can_moderate(req.user, self.store.one("SELECT * FROM users WHERE id=?", (c["author_id"],)))):
            tools += ('<form class="inl" action="/c/%d/delete" method="post">%s<input class="linkbtn s" type="submit" value="Delete"></form>') % (
                c["id"], hidden_csrf(self, req))
        if c["author_id"] != req.user["id"]:
            tools += '<a class="muted" href="/report?kind=comment&amp;id=%d">Report</a>' % c["id"]
        cm.append('<div class="cm">%s<div class="txt">%s <span class="muted small">%s</span><br>%s'
                  '<div class="tools">%s</div></div></div>' % (
                      avatar(cu, "s"), who_html(cu), when(c["created"]), render_text(c["body"]), tools))
    cm.append(('<div class="cm" id="comments"><form action="/p/%d/comment" method="post">%s<input type="hidden" name="back" value="%s">'
               '<input class="t" type="text" name="body" maxlength="%d" placeholder="Add a comment..." style="width:75%%"> '
               '<input class="btn" type="submit" value="Post comment"></form></div>') % (
        p["id"], hidden_csrf(self, req), esc(back), P.MAX_COMMENT))
    out.append('<div class="comments">%s</div>' % "".join(cm))
    out.append("</div>")
    return "".join(out)


def share_box(self, req, preset_circle=None):
    circles = my_circles(self, req.user["id"])
    boxes = "".join('<label style="margin-right:10px;white-space:nowrap"><input type="checkbox" name="circles[]" value="%d"%s> %s</label>' % (
        c["id"], " checked" if preset_circle and c["id"] == preset_circle else "", esc(c["name"])) for c in circles)
    return ('<div class="card share-box"><form action="/post" method="post">%s'
            '<textarea id="share-text" name="body" maxlength="%d" placeholder="Share what\'s new..."></textarea>'
            '<div class="aud"><label><input type="radio" name="vis" value="public"%s> <span class="chip pub">Public</span></label> '
            '<span class="muted">(everyone on %s)</span><br><label><input type="radio" name="vis" value="circles"%s> '
            '<span class="chip">Your circles:</span></label> %s</div>'
            
            '<input class="btn share" type="submit" value="Share" style="float:right"></form></div>') % (
        hidden_csrf(self, req), P.MAX_POST, "" if preset_circle else " checked", brand_html(req), " checked" if preset_circle else "", boxes or
        '<span class="muted">make some on the <a href="/circles">Circles</a> page</span>')


def suggestions(self, req):
    rows = self.store.q("SELECT * FROM users WHERE status='active' AND id<>? AND id NOT IN (SELECT m.member_id FROM circles c "
                        "JOIN circle_members m ON m.circle_id=c.id WHERE c.owner_id=?) ORDER BY RANDOM() LIMIT 5",
                        (req.user["id"], req.user["id"]))
    if not rows:
        return ""
    out = ['<div class="card"><h3>Suggestions</h3>']
    for u in rows:
        out.append('<div class="person">%s<div class="pt"><a class="who" href="/u/%s">%s</a><br><span class="muted small">@%s</span><br>'
                   '<a class="small" href="/u/%s">Add to circles</a></div></div>' % (
                       avatar(u, "s"), esc(u["username"]), esc(u["name"]), esc(u["username"]), esc(u["username"])))
    out.append("</div>")
    return "".join(out)


def more_link(rows, base):
    if len(rows) > P.PAGE:
        sep = "&amp;" if "?" in base else "?"
        return '<div style="text-align:center;margin-bottom:20px"><a class="btn grey" href="%s%sbefore=%d">More</a></div>' % (
            esc(base), sep, rows[P.PAGE - 1]["id"])
    return ""


# ---------------------------------------------------------------------------------------------
def route_get(self, req):
    path = req.path
    if path == "/":
        return self.view_home(req) if req.user else self.view_welcome(req)
    if path in ("/rules", "/terms", "/privacy", "/about"):
        return self.view_static(req, path[1:])
    if path == "/signin":
        return self.view_signin(req)
    if path == "/join":
        return self.view_join(req)
    if path == "/reset":
        return self.view_reset(req)
    r = need_user(self, req)
    if r:
        return r
    if path == "/explore":
        return self.view_explore(req)
    m = re.match(r"^/p/(\d+)$", path)
    if m:
        return self.view_post(req, int(m.group(1)))
    m = re.match(r"^/u/([A-Za-z0-9_]{1,30})$", path)
    if m:
        return self.view_profile(req, m.group(1))
    if path == "/people":
        return self.view_people(req)
    if path == "/circles":
        return self.view_circles(req)
    if path == "/notifications":
        return self.view_notifications(req)
    if path == "/settings":
        return self.view_settings(req)
    if path == "/settings/export":
        return self.view_export(req)
    if path == "/report":
        return self.view_report(req)
    if path == "/admin" and is_staff(req.user):
        return self.view_admin(req)
    return self.page(req, "Not found", '<div class="card"><h2>That page isn\'t here</h2><p><a href="/">Back to your stream</a></p></div>', code=404)


def route_post(self, req):
    path = req.path
    if path == "/signin":
        return self.do_signin(req)
    if path == "/join":
        return self.do_join(req)
    if path == "/reset":
        return self.do_reset(req)
    r = need_user(self, req)
    if not r and req.user["pw_weak"] and path not in ("/settings/password", "/signout", "/settings/signout-others"):
        return self.view_settings(req, err="Your password is too easy to guess, so your account can't post or change anything until you "
                                           "pick a new one below.")
    if r:
        return r
    if path == "/signout":
        self.store.run("DELETE FROM sessions WHERE token=?", (req.session["token"],))
        req.set_cookies.append(self.cookie_header(req, "gpsid", "", 0))
        return Reply.redirect("/")
    if path == "/post":
        return self.do_post(req)
    m = re.match(r"^/p/(\d+)/(comment|delete)$", path)
    if m:
        return self.do_comment(req, int(m.group(1))) if m.group(2) == "comment" else self.do_delete_post(req, int(m.group(1)))
    m = re.match(r"^/c/(\d+)/delete$", path)
    if m:
        return self.do_delete_comment(req, int(m.group(1)))
    if path == "/plus":
        return self.do_plus(req)
    m = re.match(r"^/people/([a-z0-9_]{3,20})/circles$", path)
    if m:
        return self.do_set_circles(req, m.group(1))
    if path.startswith("/circles/"):
        return self.do_circles(req, path[9:])
    if path.startswith("/settings"):
        return self.do_settings(req, path[9:])
    if path == "/report":
        return self.do_report(req)
    if path.startswith("/admin/") and is_staff(req.user):
        return self.do_admin(req, path[7:])
    return self.page(req, "Not found", '<div class="card"><h2>That page isn\'t here</h2></div>', code=404)


# ---- signed out ----
def view_welcome(self, req):
    body = ('<div class="welcome"><div class="pitch"><h1><span class="gp-brand">Gplex+</span></h1><p>A small community in the spirit of Google+, the way it '
            'looked in 2011 to 2013: your stream, your circles, +1s and conversations with the people you choose.</p>'
            '<p><span class="gp-brand">Gplex+</span> is invite-only. If someone gave you an invite link, open it to join.</p></div>'
            '<div class="box">%s</div></div>') % self.signin_form(req)
    return self.page(req, P.NAME, body, bare=True)


def signin_form(self, req, error="", nxt=""):
    return ('<div class="card"><h2>Sign in</h2>%s<form action="/signin" method="post">%s<input type="hidden" name="next" value="%s">'
            'Username<br><input class="t" type="text" name="username" maxlength="20" autocapitalize="off"><br><br>'
            'Password<br><input class="t" type="password" name="password" maxlength="200"><br><br>'
            '<input class="btn" type="submit" value="Sign in"></form></div>') % (
        ('<div class="err">%s</div>' % esc(error)) if error else "", hidden_csrf(self, req), esc(nxt or req.query.get("next", "")))


def view_signin(self, req):
    if req.user:
        return Reply.redirect("/")
    return self.page(req, "Sign in", '<div class="welcome"><div class="box" style="float:none;margin:0 auto">%s</div></div>' % self.signin_form(req), bare=True)


def safe_next(nxt):
    return nxt if nxt and nxt.startswith("/") and not nxt.startswith("//") else "/"


def do_signin(self, req):
    uname = (req.form.get("username") or "").strip().lower()
    ip = req.h.client_address[0]
    if self.limited("ip:" + ip) or self.limited("u:" + uname):
        return self.page(req, "Sign in", '<div class="welcome"><div class="box" style="float:none;margin:0 auto">%s</div></div>' %
                         self.signin_form(req, "Too many wrong passwords. Wait an hour and try again."), bare=True, code=429)
    u = self.store.one("SELECT * FROM users WHERE username=?", (uname,))
    if not u or not P.check_password(req.form.get("password") or "", u["pw"]) or u["status"] != "active":
        self.failed("ip:" + ip)
        self.failed("u:" + uname)
        right = u and u["status"] != "active" and P.check_password(req.form.get("password") or "", u["pw"])
        msg = ("That account is permanently banned." if u["status"] == "banned" else "That account is suspended.") if right \
            else "Wrong username or password."
        return self.page(req, "Sign in", '<div class="welcome"><div class="box" style="float:none;margin:0 auto">%s</div></div>' %
                         self.signin_form(req, msg, req.form.get("next", "")), bare=True)
    if u["role"] not in ("admin", "mod") and self.ip_banned(req):
        return self.page(req, "Sign in", '<div class="welcome"><div class="box" style="float:none;margin:0 auto">%s</div></div>' %
                         self.signin_form(req, "Gplex+ isn't available from this network."), bare=True, code=403)
    weak = 1 if P.password_problem(req.form.get("password") or "", u["username"], u["name"]) else 0
    if weak != u["pw_weak"]:
        self.store.run("UPDATE users SET pw_weak=? WHERE id=?", (weak, u["id"]))
    self.start_session(req, u["id"])
    if weak:
        return Reply.redirect("/settings?weak=1")
    return Reply.redirect(safe_next(req.form.get("next")))


def invite_row(self, code):
    if not code or not re.match(r"^[A-Za-z0-9_-]{8,64}$", code):
        return None
    row = self.store.one("SELECT * FROM invites WHERE code=? AND used_by IS NULL", (code,))
    return row if row and row["uses"] < max(1, row["max_uses"]) else None


def join_form(self, req, code, error="", f=None):
    f = f or {}
    return ('<div class="welcome"><div class="pitch"><h1>Join <span class="gp-brand">Gplex+</span></h1><p>You\'ve been invited. Pick a name people will '
            'see and a username for your profile address.</p><p class="muted">By joining you agree to the '
            '<a href="/rules">community rules</a> and <a href="/terms">terms</a>. See the <a href="/privacy">privacy</a> page for '
            'what is kept about you.</p></div><div class="box"><div class="card"><h2>Create your account</h2>%s'
            '<form action="/join" method="post">%s<input type="hidden" name="invite" value="%s">'
            'Your name<br><input class="t" type="text" name="name" maxlength="50" value="%s"><br><br>'
            'Username <span class="muted small">(3-20 letters, numbers or _)</span><br><input class="t" type="text" name="username" maxlength="20" value="%s"><br><br>'
            'Password <span class="muted small">(at least 10 characters)</span><br><input class="t" type="password" name="password" maxlength="200"><br><br>'
            'Password again<br><input class="t" type="password" name="password2" maxlength="200"><br><br>'
            '<label><input type="checkbox" name="age" value="1"> I am 13 or older (16 or older in the EU)</label><br>'
            '<label><input type="checkbox" name="rules" value="1"> I agree to the community rules and terms</label><br><br>'
            '<input class="btn" type="submit" value="Join Gplex+"></form></div></div></div>') % (
        ('<div class="err">%s</div>' % esc(error)) if error else "", hidden_csrf(self, req), esc(code),
        esc(f.get("name", "")), esc(f.get("username", "")))


def view_join(self, req):
    code = req.query.get("invite", "")
    if not invite_row(self, code):
        return self.page(req, "Join", '<div class="welcome"><div class="card"><h2>That invite isn\'t valid</h2><p>It may have been used '
                         'already. Ask the person who invited you for a new link.</p></div></div>', bare=True, code=404)
    return self.page(req, "Join", join_form(self, req, code), bare=True)


def do_join(self, req):
    code = req.form.get("invite", "")
    inv = invite_row(self, code)
    if not inv:
        return self.page(req, "Join", '<div class="welcome"><div class="card"><h2>That invite isn\'t valid</h2></div></div>', bare=True, code=404)
    name = " ".join((req.form.get("name") or "").split())[:50]
    uname = (req.form.get("username") or "").strip().lower()
    pw = req.form.get("password") or ""
    err = ""
    if not name:
        err = "Please enter your name."
    elif not P.USERNAME_RE.match(uname):
        err = "Usernames are 3-20 lowercase letters, numbers or _."
    elif self.store.one("SELECT 1 FROM users WHERE username=?", (uname,)):
        err = "That username is taken."
    elif plus_filter.check(name) or plus_filter.check(uname.replace("_", " ")) or plus_filter.check(uname):
        err = "That name or username has a word Gplex+ doesn't allow. Please pick another."
    elif plus_filter.has_link(name):
        err = "Names can't have web addresses in them."
    elif name_problem(self, name, uname, staff=bool(inv["admin"])):
        err = name_problem(self, name, uname, staff=bool(inv["admin"]))
    elif P.password_problem(pw, uname, name):
        err = P.password_problem(pw, uname, name)
    elif pw != req.form.get("password2"):
        err = "The two passwords don't match."
    elif req.form.get("age") != "1" or req.form.get("rules") != "1":
        err = "Please confirm your age and agree to the rules."
    if err:
        return self.page(req, "Join", join_form(self, req, code, err, req.form), bare=True)
    with self.store.lock:
        db = self.store.db()
        inv = db.execute("SELECT * FROM invites WHERE code=? AND used_by IS NULL", (code,)).fetchone()
        if not inv or inv["uses"] >= max(1, inv["max_uses"]):
            return self.page(req, "Join", '<div class="welcome"><div class="card"><h2>That invite was just used up</h2></div></div>', bare=True)
        if db.execute("SELECT 1 FROM users WHERE username=?", (uname,)).fetchone():
            return self.page(req, "Join", join_form(self, req, code, "That username is taken.", req.form), bare=True)
        cur = db.execute("INSERT INTO users (username, name, pw, role, created, invited_by, joined_via) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (uname, name, P.hash_password(pw), "admin" if inv["admin"] else "member", now(), inv["created_by"],
                          inv["note"] or "an invite"))
        uid = cur.lastrowid
        # a multi-use invite stays open until its last use; then it is closed like a single-use one
        uses = inv["uses"] + 1
        if uses >= max(1, inv["max_uses"]):
            db.execute("UPDATE invites SET uses=?, used_by=?, used=? WHERE code=?", (uses, uid, now(), code))
        else:
            db.execute("UPDATE invites SET uses=? WHERE code=?", (uses, code))
        for c in P.DEFAULT_CIRCLES:
            db.execute("INSERT INTO circles (owner_id, name, created) VALUES (?, ?, ?)", (uid, c, now()))
        db.commit()
    if inv["admin"]:
        self.first_invite()
    self.start_session(req, uid)
    return Reply.redirect("/people?welcome=1")


def view_reset(self, req):
    tok = req.query.get("token", "")
    row = self.store.one("SELECT * FROM resets WHERE token=? AND used IS NULL AND created>?", (P.sha(tok), now() - 7 * 86400)) if tok else None
    if not row:
        return self.page(req, "Reset", '<div class="welcome"><div class="card"><h2>That link isn\'t valid</h2><p>It may have expired '
                         '(links last a week) or been used. Ask an admin for a new one.</p></div></div>', bare=True, code=404)
    return self.page(req, "New password", ('<div class="welcome"><div class="box" style="float:none;margin:0 auto"><div class="card"><h2>Choose a new password</h2>'
                     '<form action="/reset" method="post">%s<input type="hidden" name="token" value="%s">New password<br>'
                     '<input class="t" type="password" name="password" maxlength="200"><br><br>Again<br><input class="t" type="password" '
                     'name="password2" maxlength="200"><br><br><input class="btn" type="submit" value="Save"></form></div></div></div>') % (
        hidden_csrf(self, req), esc(tok)), bare=True)


def do_reset(self, req):
    tok = req.form.get("token", "")
    row = self.store.one("SELECT * FROM resets WHERE token=? AND used IS NULL AND created>?", (P.sha(tok), now() - 7 * 86400)) if tok else None
    pw = req.form.get("password") or ""
    if not row:
        return self.page(req, "Reset", '<div class="welcome"><div class="card"><h2>That link isn\'t valid</h2></div></div>', bare=True, code=404)
    target = self.store.one("SELECT username, name FROM users WHERE id=?", (row["user_id"],))
    prob = P.password_problem(pw, target["username"] if target else "", target["name"] if target else "") or (
        "The two passwords don't match." if pw != req.form.get("password2") else None)
    if prob:
        return self.page(req, "Reset", ('<div class="welcome"><div class="card"><div class="err">' + esc(prob) + '</div>'
                         '<a href="/reset?token=%s">Try again</a></div></div>') % esc(tok), bare=True)
    self.store.run("UPDATE users SET pw=?, pw_weak=0 WHERE id=?", (P.hash_password(pw), row["user_id"]))
    self.store.run("UPDATE resets SET used=? WHERE token=?", (now(), row["token"]))
    self.store.run("DELETE FROM sessions WHERE user_id=?", (row["user_id"],))
    return Reply.redirect("/signin")


# ---- the stream ----
def view_home(self, req):
    circles = my_circles(self, req.user["id"])
    cid = req.query.get("circle")
    circle = None
    if cid and cid.isdigit():
        circle = next((c for c in circles if c["id"] == int(cid)), None)
    if circle:
        rows = query_posts(self, req, "p.author_id IN (SELECT member_id FROM circle_members WHERE circle_id=:c)", {"c": circle["id"]},
                           req.query.get("before"))
        base = "/?circle=%d" % circle["id"]
    else:
        rows = query_posts(self, req, "p.author_id=:v OR p.author_id IN (SELECT m.member_id FROM circles c JOIN circle_members m "
                           "ON m.circle_id=c.id WHERE c.owner_id=:v)", {}, req.query.get("before"))
        base = "/"
    tabs = ['<a href="/"%s>All</a>' % (' class="on"' if not circle else "")]
    for c in circles:
        tabs.append('<a href="/?circle=%d"%s>%s</a>' % (c["id"], ' class="on"' if circle and c["id"] == circle["id"] else "", esc(c["name"])))
    body = ['<div class="card streamhead"><b>Stream</b> &nbsp; %s</div>' %
            " &nbsp; ".join(tabs), share_box(self, req, circle["id"] if circle else None)]
    if not rows:
        if not req.query.get("before"):
            body.append('<div class="card"><h2>Your stream is quiet</h2><p>Add people to your circles to see their posts here, '
                        'or look around on <a href="/explore">Explore</a>, where everyone\'s public posts are.</p></div>')
    body.append('<div class="stream">%s</div>' % "".join(post_card(self, req, p, back=base) for p in rows[:P.PAGE]))
    body.append(more_link(rows, base))
    return self.page(req, "Home", "".join(body), side=suggestions(self, req), nav="home")


def view_explore(self, req):
    rows = query_posts(self, req, "p.visibility='public'", {}, req.query.get("before"))
    body = ['<div class="card streamhead"><b>Explore</b> &nbsp; '
            '<span class="muted">Everything shared publicly on %s</span></div>' % brand_html(req)]
    if not rows:
        body.append('<div class="card"><p>Nothing public yet. Be the first: share something publicly from your <a href="/">stream</a>.</p></div>')
    body.append('<div class="stream">%s</div>' % "".join(post_card(self, req, p, back="/explore") for p in rows[:P.PAGE]))
    body.append(more_link(rows, "/explore"))
    return self.page(req, "Explore", "".join(body), side=suggestions(self, req), nav="explore")


def view_post(self, req, pid):
    p = can_see(self, req, pid)
    if not p:
        return self.page(req, "Not found", '<div class="card"><h2>That post isn\'t available</h2><p>It may have been deleted, or '
                         'it wasn\'t shared with you.</p></div>', code=404)
    return self.page(req, "Post", post_card(self, req, p, full=True, back="/p/%d" % pid), side=suggestions(self, req))


def do_post(self, req):
    body = (req.form.get("body") or "").strip()[:P.MAX_POST]
    vis = req.form.get("vis") or "public"
    if not body:
        return Reply.redirect("/")
    err = BLOCKED if plus_filter.check(body) else link_wait(self, req, body)
    if err:
        return self.page(req, "Share", '<div class="card"><div class="err">%s</div><p>Your post (not shared):</p>'
                         '<textarea readonly>%s</textarea><p><a href="/">Back to your stream</a></p></div>' % (esc(err), esc(body)), nav="home")
    mine = {c["id"] for c in my_circles(self, req.user["id"])}
    chosen = [int(x) for x in req.multi("circles") if str(x).isdigit() and int(x) in mine]
    if vis == "circles" and not chosen:
        return self.page(req, "Share", '<div class="card"><div class="err">Pick at least one circle to share with, or share publicly.</div>'
                         '<a href="/">Back</a></div>', nav="home")
    pid = self.store.run("INSERT INTO posts (author_id, body, visibility, created) VALUES (?, ?, ?, ?)",
                         (req.user["id"], body, "circles" if vis == "circles" else "public", now()))
    if vis == "circles":
        for c in chosen:
            self.store.run("INSERT OR IGNORE INTO post_circles (post_id, circle_id) VALUES (?, ?)", (pid, c))
    return Reply.redirect("/" if vis != "circles" or len(chosen) != 1 else "/?circle=%d" % chosen[0])


def notify(self, user_id, actor_id, kind, post_id):
    if user_id == actor_id:
        return
    self.store.run("INSERT INTO notifications (user_id, actor_id, kind, post_id, created) VALUES (?, ?, ?, ?, ?)",
                   (user_id, actor_id, kind, post_id, now()))


def do_comment(self, req, pid):
    p = can_see(self, req, pid)
    body = (req.form.get("body") or "").strip()[:P.MAX_COMMENT]
    back = safe_next(req.form.get("back"))
    if not p or not body:
        return Reply.redirect(back)
    err = BLOCKED if plus_filter.check(body) else link_wait(self, req, body)
    if err:
        return self.page(req, "Comment", '<div class="card"><div class="err">%s</div><p>Your comment (not posted):</p>'
                         '<textarea readonly>%s</textarea><p><a href="%s">Back</a></p></div>' % (esc(err), esc(body), esc(back)))
    self.store.run("INSERT INTO comments (post_id, author_id, body, created) VALUES (?, ?, ?, ?)", (pid, req.user["id"], body, now()))
    notify(self, p["author_id"], req.user["id"], "comment", pid)
    others = self.store.q("SELECT DISTINCT author_id FROM comments WHERE post_id=? AND author_id NOT IN (?, ?) AND removed=0 LIMIT 50",
                          (pid, req.user["id"], p["author_id"]))
    for o in others:
        if can_see_as(self, o["author_id"], pid):
            notify(self, o["author_id"], req.user["id"], "reply", pid)
    return Reply.redirect(back + ("#p%d" % pid if back != "/p/%d" % pid else "#comments"))


def can_see_as(self, uid, pid):
    return self.store.one("SELECT 1 FROM posts p JOIN users a ON a.id=p.author_id WHERE p.id=:id AND " + VISIBLE, {"id": pid, "v": uid})


def delete_post_fully(self, pid):
    p = self.store.one("SELECT * FROM posts WHERE id=?", (pid,))
    if not p:
        return
    cids = [r["id"] for r in self.store.q("SELECT id FROM comments WHERE post_id=?", (pid,))]
    for c in cids:
        self.store.run("DELETE FROM plusones WHERE kind='comment' AND target_id=?", (c,))
    self.store.run("DELETE FROM comments WHERE post_id=?", (pid,))
    self.store.run("DELETE FROM plusones WHERE kind='post' AND target_id=?", (pid,))
    self.store.run("DELETE FROM post_circles WHERE post_id=?", (pid,))
    self.store.run("DELETE FROM notifications WHERE post_id=?", (pid,))
    self.store.run("DELETE FROM posts WHERE id=?", (pid,))
    self.store.delete_image(p["image"])


def do_delete_post(self, req, pid):
    p = self.store.one("SELECT * FROM posts WHERE id=?", (pid,))
    if p and p["author_id"] == req.user["id"]:
        delete_post_fully(self, pid)
    elif p and can_moderate(req.user, self.store.one("SELECT * FROM users WHERE id=?", (p["author_id"],))):
        self.store.run("UPDATE posts SET removed=1 WHERE id=?", (pid,))
    return Reply.redirect("/")


def do_delete_comment(self, req, cid):
    c = self.store.one("SELECT c.*, p.author_id AS post_author FROM comments c JOIN posts p ON p.id=c.post_id WHERE c.id=?", (cid,))
    if c and (c["author_id"] == req.user["id"] or c["post_author"] == req.user["id"]):
        self.store.run("DELETE FROM plusones WHERE kind='comment' AND target_id=?", (cid,))
        self.store.run("DELETE FROM comments WHERE id=?", (cid,))
    elif c and can_moderate(req.user, self.store.one("SELECT * FROM users WHERE id=?", (c["author_id"],))):
        self.store.run("UPDATE comments SET removed=1 WHERE id=?", (cid,))
    return Reply.redirect("/p/%d" % c["post_id"] if c else "/")


def do_plus(self, req):
    kind = req.form.get("kind")
    tid = req.form.get("id", "")
    back = safe_next(req.form.get("back"))
    if kind not in ("post", "comment") or not tid.isdigit():
        return Reply.redirect(back)
    tid = int(tid)
    if kind == "post":
        p = can_see(self, req, tid)
        owner, pid = (p["author_id"], tid) if p else (None, None)
    else:
        c = self.store.one("SELECT * FROM comments WHERE id=? AND removed=0", (tid,))
        p = can_see(self, req, c["post_id"]) if c else None
        owner, pid = (c["author_id"], c["post_id"]) if (c and p) else (None, None)
    if not owner:
        return Reply.redirect(back)
    if self.store.one("SELECT 1 FROM plusones WHERE kind=? AND target_id=? AND user_id=?", (kind, tid, req.user["id"])):
        self.store.run("DELETE FROM plusones WHERE kind=? AND target_id=? AND user_id=?", (kind, tid, req.user["id"]))
    else:
        self.store.run("INSERT OR IGNORE INTO plusones (kind, target_id, user_id, created) VALUES (?, ?, ?, ?)", (kind, tid, req.user["id"], now()))
        notify(self, owner, req.user["id"], "plus_" + kind, pid)
    return Reply.redirect(back + ("#p%d" % pid if not back.startswith("/p/") else ""))


# ---- people and circles ----
def circle_form(self, req, u, circles, inmine):
    boxes = "".join('<label><input type="checkbox" name="circles[]" value="%d"%s> %s</label>' % (
        c["id"], " checked" if c["id"] in inmine else "", esc(c["name"])) for c in circles)
    return ('<form class="circ" action="/people/%s/circles" method="post">%s<input type="hidden" name="back" value="%s">%s '
            '<input class="btn grey" type="submit" value="Save" style="padding:2px 8px"></form>') % (
        esc(u["username"]), hidden_csrf(self, req), esc(req.path + (("?" + P.urllib.parse.urlencode(req.query)) if req.query else "")), boxes)


def view_people(self, req):
    q = (req.query.get("q") or "").strip()
    circles = my_circles(self, req.user["id"])
    member_of = {}
    for r in self.store.q("SELECT m.member_id, m.circle_id FROM circle_members m JOIN circles c ON c.id=m.circle_id WHERE c.owner_id=?", (req.user["id"],)):
        member_of.setdefault(r["member_id"], set()).add(r["circle_id"])
    if q:
        like = "%" + q.replace("%", "").replace("_", "") + "%"
        rows = self.store.q("SELECT * FROM users WHERE status='active' AND id<>? AND (name LIKE ? OR username LIKE ?) ORDER BY name LIMIT 100",
                            (req.user["id"], like, like))
    else:
        rows = self.store.q("SELECT * FROM users WHERE status='active' AND id<>? ORDER BY created DESC LIMIT 200", (req.user["id"],))
    out = []
    if req.query.get("welcome"):
        out.append('<div class="ok"><b>Welcome to ' + brand_html(req) + '!</b> Add people to your circles so their posts show up in your stream. '
                   'Then share something from <a href="/">Home</a>.</div>')
    out.append('<div class="card"><h2>%s</h2>' % ("People matching \"%s\"" % esc(q) if q else "Everyone on " + brand_html(req)))
    if not rows:
        out.append('<p class="muted">%s</p>' % ("Nobody found." if q else "It's just you so far. Invite some people!"))
    for u in rows:
        out.append('<div class="person">%s<div class="pt"><a class="who" href="/u/%s">%s</a> <span class="muted small">@%s</span>%s%s</div></div>' % (
            avatar(u), esc(u["username"]), esc(u["name"]), esc(u["username"]),
            ('<div class="small muted" style="margin-top:3px">%s</div>' % esc(u["about"][:140])) if u["about"] else "",
            circle_form(self, req, u, circles, member_of.get(u["id"], set()))))
    out.append("</div>")
    return self.page(req, "People", "".join(out), nav="people")


def do_set_circles(self, req, username):
    u = get_user(self, username)
    back = safe_next(req.form.get("back"))
    if not u or u["id"] == req.user["id"]:
        return Reply.redirect(back)
    mine = {c["id"] for c in my_circles(self, req.user["id"])}
    want = {int(x) for x in req.multi("circles") if str(x).isdigit() and int(x) in mine}
    before = {r["circle_id"] for r in self.store.q("SELECT m.circle_id FROM circle_members m JOIN circles c ON c.id=m.circle_id "
                                                    "WHERE c.owner_id=? AND m.member_id=?", (req.user["id"], u["id"]))}
    for c in before - want:
        self.store.run("DELETE FROM circle_members WHERE circle_id=? AND member_id=?", (c, u["id"]))
    for c in want - before:
        self.store.run("INSERT OR IGNORE INTO circle_members (circle_id, member_id, added) VALUES (?, ?, ?)", (c, u["id"], now()))
    if want and not before:
        notify(self, u["id"], req.user["id"], "circled", None)
    return Reply.redirect(back)


def view_circles(self, req):
    circles = my_circles(self, req.user["id"])
    out = ['<div class="card"><h2>Your circles</h2><div class="bubbles">']
    for c in circles:
        out.append('<a class="bubble" href="/?circle=%d" style="text-decoration:none"><b>%s</b><span>%d %s</span></a>' % (
            c["id"], esc(c["name"]), c["n"], "person" if c["n"] == 1 else "people"))
    out.append('</div><form action="/circles/new" method="post">%s<input class="t" type="text" name="name" maxlength="40" '
               'placeholder="New circle name" style="width:220px"> <input class="btn" type="submit" value="Create circle"></form></div>' %
               hidden_csrf(self, req))
    for c in circles:
        members = self.store.q("SELECT u.* FROM circle_members m JOIN users u ON u.id=m.member_id WHERE m.circle_id=? AND u.status='active' "
                               "ORDER BY u.name", (c["id"],))
        names = " ".join('<a class="chip" href="/u/%s">%s</a>' % (esc(m["username"]), esc(m["name"])) for m in members) or \
            '<span class="muted">Nobody yet - add people from <a href="/people">People</a>.</span>'
        out.append(('<div class="card"><h3>%s</h3><p>%s</p><form action="/circles/%d/rename" method="post" style="display:inline">%s'
                    '<input class="t" type="text" name="name" maxlength="40" value="%s" style="width:160px"> <input class="btn grey" type="submit" value="Rename"></form> '
                    '<form action="/circles/%d/delete" method="post" style="display:inline">%s<input class="btn grey" type="submit" value="Delete circle"></form></div>') % (
            esc(c["name"]), names, c["id"], hidden_csrf(self, req), esc(c["name"]), c["id"], hidden_csrf(self, req)))
    added = self.store.q("SELECT DISTINCT u.* FROM circle_members m JOIN circles c ON c.id=m.circle_id JOIN users u ON u.id=c.owner_id "
                         "WHERE m.member_id=? AND u.status='active' ORDER BY u.name", (req.user["id"],))
    side = '<div class="card"><h3>Have you in circles</h3>%s</div>' % ("".join(
        '<div class="person">%s<div class="pt"><a class="who" href="/u/%s">%s</a></div></div>' % (avatar(u, "s"), esc(u["username"]), esc(u["name"])) for u in added)
        or '<p class="muted">Nobody yet.</p>')
    return self.page(req, "Circles", "".join(out), side=side, nav="circles")


def do_circles(self, req, rest):
    uid = req.user["id"]
    if rest == "new":
        name = " ".join((req.form.get("name") or "").split())[:40]
        if plus_filter.check(name):
            return self.page(req, "Circles", '<div class="card"><div class="err">%s</div><a href="/circles">Back</a></div>' % esc(BLOCKED), nav="circles")
        if name and len(my_circles(self, uid)) < 50:
            self.store.run("INSERT INTO circles (owner_id, name, created) VALUES (?, ?, ?)", (uid, name, now()))
        return Reply.redirect("/circles")
    m = re.match(r"^(\d+)/(rename|delete)$", rest)
    if m:
        c = self.store.one("SELECT * FROM circles WHERE id=? AND owner_id=?", (int(m.group(1)), uid))
        if c and m.group(2) == "rename":
            name = " ".join((req.form.get("name") or "").split())[:40]
            if plus_filter.check(name):
                return self.page(req, "Circles", '<div class="card"><div class="err">%s</div><a href="/circles">Back</a></div>' % esc(BLOCKED), nav="circles")
            if name:
                self.store.run("UPDATE circles SET name=? WHERE id=?", (name, c["id"]))
        elif c:
            self.store.run("DELETE FROM circle_members WHERE circle_id=?", (c["id"],))
            self.store.run("DELETE FROM post_circles WHERE circle_id=?", (c["id"],))
            self.store.run("DELETE FROM circles WHERE id=?", (c["id"],))
    return Reply.redirect("/circles")


def view_profile(self, req, username):
    u = get_user(self, username)
    if not u:
        return self.page(req, "Not found", '<div class="card"><h2>Nobody here by that name</h2></div>', code=404)
    rows = query_posts(self, req, "p.author_id=:a", {"a": u["id"]}, req.query.get("before"))
    cover = '<div class="cover"></div>'
    incircles = self.store.one("SELECT COUNT(DISTINCT c.owner_id) AS n FROM circle_members m JOIN circles c ON c.id=m.circle_id "
                               "JOIN users o ON o.id=c.owner_id AND o.status='active' WHERE m.member_id=?", (u["id"],))["n"]
    head = ['<div class="card">', cover, '<div class="prof">', avatar(u, "l"), '<div class="pt"><h1>%s%s</h1>' % (esc(u["name"]),
            {"admin": ' <span class="badge">Admin</span>', "mod": ' <span class="badge mod">Moderator</span>'}.get(u["role"], "")),
            '<div class="muted">@%s - in %d %s circles - joined %s</div>' % (esc(u["username"]), incircles, "person's" if incircles == 1 else "people's",
                                                                              when(u["created"]))]
    if u["about"]:
        head.append('<div class="about">%s</div>' % render_text(u["about"]))
    if u["id"] != req.user["id"]:
        circles = my_circles(self, req.user["id"])
        inmine = {r["circle_id"] for r in self.store.q("SELECT m.circle_id FROM circle_members m JOIN circles c ON c.id=m.circle_id "
                                                        "WHERE c.owner_id=? AND m.member_id=?", (req.user["id"], u["id"]))}
        head.append('<div class="pacts"><b>Your circles:</b>%s<div style="margin-top:6px"><a class="small muted" href="/report?kind=user&amp;id=%d">'
                    'Report profile</a></div></div>' % (circle_form(self, req, u, circles, inmine), u["id"]))
    else:
        head.append('<div class="pacts"><a class="btn grey" href="/settings">Edit profile</a></div>')
    head.append('</div><div class="clr"></div></div></div>')
    body = ["".join(head)]
    body.append('<div class="stream">%s</div>' % "".join(post_card(self, req, p, back="/u/" + u["username"]) for p in rows[:P.PAGE]))
    if not rows:
        body.append('<div class="card"><p class="muted">No posts to show.</p></div>')
    body.append(more_link(rows, "/u/" + u["username"]))
    return self.page(req, u["name"], "".join(body), nav="profile" if u["id"] == req.user["id"] else None)


def view_notifications(self, req):
    rows = self.store.q("SELECT n.*, a.username, a.name, a.avatar, a.role, a.id AS uid FROM notifications n JOIN users a ON a.id=n.actor_id "
                        "WHERE n.user_id=? AND a.status='active' ORDER BY n.id DESC LIMIT 100", (req.user["id"],))
    words = {"plus_post": "+1'd your post", "plus_comment": "+1'd your comment", "comment": "commented on your post",
             "reply": "also commented on a post", "circled": "added you to their circles"}
    out = ['<div class="card"><h2>Notifications</h2>']
    if not rows:
        out.append('<p class="muted">Nothing yet.</p>')
    for n in rows:
        u = user_row(n)
        target = ('<a href="/p/%d">%s</a>' % (n["post_id"], words.get(n["kind"], ""))) if n["post_id"] else words.get(n["kind"], "")
        out.append('<div class="person"%s>%s<div class="pt"><a class="who" href="/u/%s">%s</a> %s<br><span class="muted small">%s</span></div></div>' % (
            ' style="background:#fdf6e3"' if not n["seen"] else "", avatar(u, "s"), esc(u["username"]), esc(u["name"]), target, when(n["created"])))
    out.append("</div>")
    self.store.run("UPDATE notifications SET seen=1 WHERE user_id=? AND seen=0", (req.user["id"],))
    return self.page(req, "Notifications", "".join(out), nav="notifications")


# ---- settings, export, deleting the account ----
def browser_of(ua):
    """A short name for a browser from its User-Agent: "Safari on iPhone (iOS 18.5)", "Firefox on Windows"."""
    ua = ua or ""
    dev = ("iPhone" if "iPhone" in ua else "iPad" if "iPad" in ua else "Android" if "Android" in ua else
           "Windows" if "Windows" in ua else "Mac" if "Macintosh" in ua else "Linux" if "Linux" in ua else "an unknown device")
    m = re.search(r"OS (\d+)[_.](\d+)", ua)
    if dev in ("iPhone", "iPad") and m:
        dev += " (iOS %s.%s)" % (m.group(1), m.group(2))
    app = ("Edge" if "Edg/" in ua else "Opera" if "OPR/" in ua else "Firefox" if ("Firefox/" in ua or "FxiOS" in ua) else
           "Chrome" if ("Chrome/" in ua or "CriOS" in ua) else "Safari" if "Safari/" in ua else "a browser")
    return "%s on %s" % (app, dev)


def view_settings(self, req, msg="", err=""):
    u = req.user
    c = hidden_csrf(self, req)
    out = []
    if msg:
        out.append('<div class="ok">%s</div>' % esc(msg))
    if err:
        out.append('<div class="err">%s</div>' % esc(err))
    elif req.query.get("weak") and u["pw_weak"]:
        out.append('<div class="err">Your password is too easy to guess, so your account can\'t post or change anything until you pick a new one '
                   'below.</div>')
    out.append(('<div class="card"><h2>Profile</h2><form action="/settings/profile" method="post">%s'
                'Name<br><input class="t" type="text" name="name" maxlength="50" value="%s"><br><br>'
                'About you<br><textarea name="about" maxlength="1000">%s</textarea><br><br>'
                                '<input class="btn" type="submit" value="Save profile"></form></div>') % (
        c, esc(u["name"]), esc(u["about"])))
    out.append(('<div class="card"><h2>Site name</h2><form action="/settings/brand" method="post">%s'
                '<p>The name this site goes by on your screen: the logo, page titles and so on. It only changes what you see. '
                'Leave it empty for the usual name, %s.</p>'
                '<input class="t" type="text" name="brand" maxlength="%d" value="%s" style="width:200px"> '
                '<input class="btn" type="submit" value="Save name"></form></div>') % (
        c, esc(P.NAME), P.BRAND_MAX, esc(u["brand"] if "brand" in u.keys() else "")))
    out.append(('<div class="card" id="password"><h2>Password</h2><form action="/settings/password" method="post">%s'
                'Current password<br><input class="t" type="password" name="old" maxlength="200"><br><br>'
                'New password <span class="muted small">(at least 10 characters, not your name or username; a few random words work well)</span><br><input class="t" type="password" name="new" maxlength="200"><br><br>'
                'New password again<br><input class="t" type="password" name="new2" maxlength="200"><br><br>'
                '<input class="btn" type="submit" value="Change password"></form></div>') % c)
    sess = self.store.q("SELECT * FROM sessions WHERE user_id=? ORDER BY seen DESC LIMIT 30", (u["id"],))
    rows = "".join('<tr><td>%s%s</td><td class="small">signed in %s<br>last used %s</td></tr>' % (
        esc(browser_of(s["ua"])), ' <b class="small" style="color:#3d9400">(this one)</b>' if s["token"] == req.session["token"] else "",
        when(s["created"]), when(s["seen"])) for s in sess)
    out.append(('<div class="card"><h2>Where you\'re signed in</h2><p class="muted small">If you see one that isn\'t you, sign out everywhere '
                'else and change your password.</p><table class="list">%s</table><form action="/settings/signout-others" method="post" style="margin-top:10px">%s'
                '<input class="btn grey" type="submit" value="Sign out everywhere else"></form></div>') % (rows, c))
    out.append(('<div class="card"><h2>Your data</h2><p><a class="btn grey" href="/settings/export">Download your data</a> '
                '<span class="muted">(your profile, posts, comments and circles, as a JSON file)</span></p>'
                '<h3 style="margin-top:16px">Delete your account</h3><p>This removes your profile, posts, comments, +1s and circles '
                'for good.</p><form action="/settings/delete" method="post">%s Type your username to confirm<br>'
                '<input class="t" type="text" name="confirm" maxlength="20" style="width:200px"><br>Password<br>'
                '<input class="t" type="password" name="password" maxlength="200" style="width:200px"><br><br>'
                '<input class="btn red" type="submit" value="Delete my account"></form></div>') % c)
    return self.page(req, "Settings", "".join(out), nav="settings")


def do_settings(self, req, rest):
    u = req.user
    if rest == "/profile":
        name = " ".join((req.form.get("name") or "").split())[:50] or u["name"]
        about = (req.form.get("about") or "").strip()[:1000]
        if plus_filter.check(name) or plus_filter.check(about):
            return self.view_settings(req, err=BLOCKED)
        wait = link_wait(self, req, name, about)
        if wait:
            return self.view_settings(req, err=wait)
        if name != u["name"]:
            prob = name_problem(self, name, uid=u["id"], staff=u["role"] in ("admin", "mod"))
            if prob:
                return self.view_settings(req, err=prob)
        self.store.run("UPDATE users SET name=?, about=? WHERE id=?", (name, about, u["id"]))
        req.user = self.store.one("SELECT * FROM users WHERE id=?", (u["id"],))
        return self.view_settings(req, msg="Profile saved.")
    if rest == "/brand":
        if plus_filter.check(req.form.get("brand") or ""):
            return self.view_settings(req, err=BLOCKED)
        self.store.run("UPDATE users SET brand=? WHERE id=?", (P.clean_brand(req.form.get("brand")), u["id"]))
        req.user = self.store.one("SELECT * FROM users WHERE id=?", (u["id"],))
        return self.view_settings(req, msg="Site name saved.")
    if rest == "/password":
        if not P.check_password(req.form.get("old") or "", u["pw"]):
            return self.view_settings(req, err="Your current password isn't right.")
        new = req.form.get("new") or ""
        prob = P.password_problem(new, u["username"], u["name"]) or ("The two new passwords don't match." if new != req.form.get("new2") else None)
        if prob:
            return self.view_settings(req, err=prob)
        self.store.run("UPDATE users SET pw=?, pw_weak=0 WHERE id=?", (P.hash_password(new), u["id"]))
        self.store.run("DELETE FROM sessions WHERE user_id=? AND token<>?", (u["id"], req.session["token"]))
        return self.view_settings(req, msg="Password changed. You were signed out everywhere else.")
    if rest == "/signout-others":
        self.store.run("DELETE FROM sessions WHERE user_id=? AND token<>?", (u["id"], req.session["token"]))
        return self.view_settings(req, msg="Signed out everywhere else.")
    if rest == "/delete":
        if (req.form.get("confirm") or "").strip().lower() != u["username"] or not P.check_password(req.form.get("password") or "", u["pw"]):
            return self.view_settings(req, err="To delete your account, type your username and your password.")
        delete_account(self, u["id"])
        req.set_cookies.append(self.cookie_header(req, "gpsid", "", 0))
        return Reply.redirect("/")
    return Reply.redirect("/settings")


def delete_account(self, uid):
    u = self.store.one("SELECT * FROM users WHERE id=?", (uid,))
    for p in self.store.q("SELECT id FROM posts WHERE author_id=?", (uid,)):
        delete_post_fully(self, p["id"])
    for c in self.store.q("SELECT id FROM comments WHERE author_id=?", (uid,)):
        self.store.run("DELETE FROM plusones WHERE kind='comment' AND target_id=?", (c["id"],))
    self.store.run("DELETE FROM comments WHERE author_id=?", (uid,))
    self.store.run("DELETE FROM plusones WHERE user_id=?", (uid,))
    for c in self.store.q("SELECT id FROM circles WHERE owner_id=?", (uid,)):
        self.store.run("DELETE FROM circle_members WHERE circle_id=?", (c["id"],))
        self.store.run("DELETE FROM post_circles WHERE circle_id=?", (c["id"],))
    self.store.run("DELETE FROM circles WHERE owner_id=?", (uid,))
    self.store.run("DELETE FROM circle_members WHERE member_id=?", (uid,))
    self.store.run("DELETE FROM notifications WHERE user_id=? OR actor_id=?", (uid, uid))
    self.store.run("DELETE FROM sessions WHERE user_id=?", (uid,))
    self.store.run("DELETE FROM resets WHERE user_id=?", (uid,))
    self.store.run("DELETE FROM user_ips WHERE user_id=?", (uid,))
    self.store.run("UPDATE reports SET reporter_id=NULL WHERE reporter_id=?", (uid,))
    if u:
        self.store.delete_image(u["avatar"])
        self.store.delete_image(u["cover"])
    self.store.run("DELETE FROM users WHERE id=?", (uid,))


def view_export(self, req):
    u = req.user
    data = {
        "exported": P.datetime.datetime.now().isoformat(timespec="seconds"),
        "profile": {"username": u["username"], "name": u["name"], "about": u["about"], "joined": u["created"],
                    },
        "posts": [dict(id=p["id"], body=p["body"], visibility=p["visibility"], created=p["created"])
                  for p in self.store.q("SELECT * FROM posts WHERE author_id=? ORDER BY id", (u["id"],))],
        "comments": [dict(id=c["id"], post=c["post_id"], body=c["body"], created=c["created"])
                     for c in self.store.q("SELECT * FROM comments WHERE author_id=? ORDER BY id", (u["id"],))],
        "circles": [{"name": c["name"], "members": [m["username"] for m in self.store.q(
            "SELECT u.username FROM circle_members m JOIN users u ON u.id=m.member_id WHERE m.circle_id=?", (c["id"],))]}
            for c in my_circles(self, u["id"])],
    }
    r = Reply(200, json.dumps(data, indent=1, ensure_ascii=False), "application/json; charset=utf-8")
    r.headers.append(("Content-Disposition", 'attachment; filename="gplex-plus-%s.json"' % u["username"]))
    return r


def view_report(self, req):
    kind = req.query.get("kind")
    tid = req.query.get("id", "")
    if kind not in ("post", "comment", "user") or not tid.isdigit():
        return Reply.redirect("/")
    return self.page(req, "Report", ('<div class="card"><h2>Report this %s</h2><p>Tell the admins what\'s wrong. Reports are private: '
                     'the person you report isn\'t told who reported them.</p><form action="/report" method="post">%s'
                     '<input type="hidden" name="kind" value="%s"><input type="hidden" name="id" value="%s">'
                     '<select name="why"><option>Spam</option><option>Harassment or bullying</option><option>Hate speech</option>'
                     '<option>Sexual content</option><option>Violence or threats</option><option>Illegal content</option>'
                     '<option>Pretending to be someone</option><option>Something else</option></select><br><br>'
                     'Details (optional)<br><textarea name="details" maxlength="1000"></textarea><br><br>'
                     '<input class="btn red" type="submit" value="Send report"></form></div>') % (
        esc(kind), hidden_csrf(self, req), esc(kind), esc(tid)))


def do_report(self, req):
    kind = req.form.get("kind")
    tid = req.form.get("id", "")
    if kind in ("post", "comment", "user") and tid.isdigit():
        reason = ((req.form.get("why") or "Something else")[:60] + ": " + (req.form.get("details") or "").strip()[:1000]).strip(": ")
        self.store.run("INSERT INTO reports (reporter_id, kind, target_id, reason, created) VALUES (?, ?, ?, ?, ?)",
                       (req.user["id"], kind, int(tid), reason, now()))
    return self.page(req, "Report", '<div class="card"><h2>Thanks</h2><p>Your report was sent to the moderators.</p><p><a href="/">Back to your stream</a></p></div>')


def report_target(self, r):
    if r["kind"] == "post":
        p = self.store.one("SELECT p.*, a.username, a.name FROM posts p JOIN users a ON a.id=p.author_id WHERE p.id=?", (r["target_id"],))
        if not p:
            return "(post deleted)", None
        return ('<b>%s</b>: %s%s%s' % (esc(p["name"]), esc(p["body"][:300]), "",
                                       ' <span class="muted">(removed)</span>' if p["removed"] else "")), p["author_id"]
    if r["kind"] == "comment":
        c = self.store.one("SELECT c.*, a.username, a.name FROM comments c JOIN users a ON a.id=c.author_id WHERE c.id=?", (r["target_id"],))
        if not c:
            return "(comment deleted)", None
        return ('<b>%s</b> on <a href="/p/%d">post %d</a>: %s%s' % (esc(c["name"]), c["post_id"], c["post_id"], esc(c["body"][:300]),
                                                                ' <span class="muted">(removed)</span>' if c["removed"] else "")), c["author_id"]
    u = self.store.one("SELECT * FROM users WHERE id=?", (r["target_id"],))
    return ('profile of <a href="/u/%s">%s</a>' % (esc(u["username"]), esc(u["name"])) if u else "(account deleted)"), (u["id"] if u else None)


def view_admin(self, req, msg=""):
    c = hidden_csrf(self, req)
    me = req.user
    admin = is_admin(me)
    out = []
    if msg:
        out.append('<div class="ok">%s</div>' % msg)
    reps = self.store.q("SELECT r.*, u.username AS by_user FROM reports r LEFT JOIN users u ON u.id=r.reporter_id WHERE r.status='open' ORDER BY r.id")
    out.append('<div class="card"><h2>Open reports (%d)</h2>' % len(reps))
    if not reps:
        out.append('<p class="muted">None. All quiet.</p>')
    for r in reps:
        what, author = report_target(self, r)
        au = self.store.one("SELECT * FROM users WHERE id=?", (author,)) if author else None
        allowed = au is None or can_moderate(me, au)
        acts = []
        if r["kind"] in ("post", "comment") and allowed:
            acts.append('<form action="/admin/remove" method="post" style="display:inline">%s<input type="hidden" name="kind" value="%s">'
                        '<input type="hidden" name="id" value="%d"><input type="hidden" name="report" value="%d">'
                        '<input class="btn red" type="submit" value="Remove it"></form>' % (c, r["kind"], r["target_id"], r["id"]))
        if au and allowed and au["status"] == "active":
            acts.append('<form action="/admin/user" method="post" style="display:inline">%s<input type="hidden" name="id" value="%d">'
                        '<input type="hidden" name="do" value="suspend"><input type="hidden" name="report" value="%d">'
                        '<input class="btn red" type="submit" value="Suspend the author"></form>' % (c, author, r["id"]))
        if au and allowed and admin and au["status"] != "banned":
            for do, label in (("ban", "Ban the author permanently"), ("banip", "Ban author and IP")):
                acts.append('<form action="/admin/user" method="post" style="display:inline">%s<input type="hidden" name="id" value="%d">'
                            '<input type="hidden" name="do" value="%s"><input type="hidden" name="report" value="%d">'
                            '<input class="btn red" type="submit" value="%s"></form>' % (c, author, do, r["id"], label))
        acts.append('<form action="/admin/resolve" method="post" style="display:inline">%s<input type="hidden" name="report" value="%d">'
                    '<input class="btn grey" type="submit" value="Dismiss"></form>' % (c, r["id"]))
        if not allowed:
            acts.append('<span class="small muted">This is about %s; only an admin can remove it or suspend them.</span>' % (
                "an admin" if au["role"] == "admin" else "a moderator"))
        out.append('<div class="person"><div class="small muted">%s report by %s - %s</div><div style="margin:4px 0">%s</div>'
                   '<div class="small" style="margin-bottom:6px">Reason: %s</div>%s</div>' % (
                       esc(r["kind"]), esc(r["by_user"] or "a deleted account"), when(r["created"]), what, esc(r["reason"]), " ".join(acts)))
    out.append("</div>")
    if admin:
        admin_invites(self, req, out, c)
    users = self.store.q("SELECT * FROM users ORDER BY created DESC LIMIT 500")
    ipbanned = {r["user_id"] for r in self.store.q("SELECT DISTINCT user_id FROM ip_bans WHERE user_id IS NOT NULL")}
    # names that pass for another member's (look-alike letters and all): the older account is the real one
    owners = {}
    for x in sorted(users, key=lambda x: x["created"]):
        for k in (plus_filter.skeleton(x["username"]), plus_filter.skeleton(x["name"])):
            owners.setdefault(k, x)
    lookalike = {}
    for x in users:
        for k in (plus_filter.skeleton(x["name"]), plus_filter.skeleton(x["username"])):
            o = owners.get(k)
            if o and o["id"] != x["id"] and x["id"] not in lookalike:
                lookalike[x["id"]] = o["username"]
    out.append('<div class="card"><h2>Members (%d)</h2>%s<table class="list members">' % (len(users), "" if admin else
               '<p class="muted small" style="margin:0 0 6px">As a moderator you can suspend members (not moderators or admins).</p>'))
    btn = ('<form action="/admin/user" method="post" style="display:inline">%s<input type="hidden" name="id" value="%%d">'
           '<input type="hidden" name="do" value="%%s"><input class="btn grey" type="submit" value="%%s" style="padding:2px 6px"></form>') % c
    for u in users:
        acts = []
        if can_moderate(me, u) and u["status"] != "banned":
            acts.append(btn % (u["id"], "unsuspend" if u["status"] != "active" else "suspend", "Unsuspend" if u["status"] != "active" else "Suspend"))
        if admin and can_moderate(me, u):
            if u["status"] == "banned":
                acts.append(btn % (u["id"], "unban", "Lift ban"))
            else:
                acts.append(btn.replace('class="btn grey"', 'class="btn red"') % (u["id"], "ban", "Ban permanently"))
                acts.append(btn.replace('class="btn grey"', 'class="btn red"') % (u["id"], "banip", "Ban IP and user"))
        if admin and u["id"] != me["id"]:
            if u["role"] == "member":
                acts.append(btn % (u["id"], "mod", "Make moderator"))
                acts.append(btn % (u["id"], "admin", "Make admin"))
            elif u["role"] == "mod":
                acts.append(btn % (u["id"], "admin", "Make admin"))
                acts.append(btn % (u["id"], "member", "Remove moderator"))
            else:
                acts.append(btn % (u["id"], "member", "Remove admin"))
        if admin:
            acts.append(btn % (u["id"], "reset", "Password link"))
        role = ROLE_NAMES.get(u["role"], u["role"])
        warn = (' <b style="color:#dd4b39" title="This name looks like another member\'s">looks like @%s</b>' % esc(lookalike[u["id"]])) if u["id"] in lookalike else ""
        out.append('<tr><td><a href="/u/%s">%s</a><br><span class="muted small">@%s</span>%s</td><td class="small">%s%s<br>joined %s%s</td><td>%s</td></tr>' % (
            esc(u["username"]), esc(u["name"]), esc(u["username"]), warn, ("<b>%s</b>" % esc(role)) if u["role"] != "member" else esc(role),
            (' - <b style="color:#dd4b39">%s</b>' % ("banned" + (" (and IP)" if u["id"] in ipbanned else "") if u["status"] == "banned" else "suspended"))
            if u["status"] != "active" else "", when(u["created"]),
            (' <span class="muted">via %s</span>' % esc(u["joined_via"])) if u["joined_via"] else "", " ".join(acts)))
    out.append("</table></div>")
    return self.page(req, "Admin" if admin else "Moderate", "".join(out), nav="admin")


def admin_ban(self, req, target, do, resolve):
    """Permanent bans (admins only). The account can't be used again; with the IP ban, the networks it was
    used from (as recorded over the last six months) can't make or use accounts either."""
    me = req.user
    c = hidden_csrf(self, req)
    if do == "unban":
        self.store.run("UPDATE users SET status='active' WHERE id=?", (target["id"],))
        n = self.store.run("DELETE FROM ip_bans WHERE user_id=?", (target["id"],))
        return self.view_admin(req, "Ban lifted for %s." % esc(target["name"]))
    ip_too = do == "banip"
    if req.form.get("confirm") != "1":
        nets = self.store.one("SELECT COUNT(*) AS n FROM user_ips WHERE user_id=?", (target["id"],))["n"]
        body = ('<div class="card"><h2>%s</h2><p><b>%s</b> (@%s) won\'t be able to sign in again, and their posts, comments and profile '
                'disappear for everyone. You can lift the ban later from the member list.</p>%s'
                '<form action="/admin/user" method="post">%s<input type="hidden" name="id" value="%d"><input type="hidden" name="do" value="%s">'
                '<input type="hidden" name="confirm" value="1"><input type="hidden" name="report" value="%s">'
                '<input class="btn red" type="submit" value="%s"> <a class="btn grey" href="/admin">Cancel</a></form></div>') % (
            "Ban IP and user?" if ip_too else "Ban permanently?", esc(target["name"]), esc(target["username"]),
            ('<p>The IP ban also blocks the %s they used Gplex+ from in the last six months: nobody there can sign in or join '
             '(admins and moderators still can). Addresses on your own home network are never banned.</p>' % (
                 "%d network%s" % (nets, "" if nets == 1 else "s") if nets else "networks (none recorded yet, so only the account is banned)")) if ip_too else "",
            c, target["id"], do, esc(req.form.get("report") or ""), "Ban IP and user" if ip_too else "Ban permanently")
        return self.page(req, "Ban", body, nav="admin")
    self.store.run("UPDATE users SET status='banned' WHERE id=?", (target["id"],))
    self.store.run("DELETE FROM sessions WHERE user_id=?", (target["id"],))
    resolve(req.form.get("report"), "author banned" + (" with IP" if ip_too else ""))
    msg = "%s is permanently banned." % esc(target["name"])
    if ip_too:
        mine = self.ip_tag(self.ip_of(req)) if self.ip_public(self.ip_of(req)) else None
        tags = [r["tag"] for r in self.store.q("SELECT tag FROM user_ips WHERE user_id=?", (target["id"],))]
        skipped = mine in tags
        n = 0
        for t in tags:
            if t == mine:
                continue
            self.store.run("INSERT OR IGNORE INTO ip_bans (tag, user_id, created, by_id) VALUES (?, ?, ?, ?)", (t, target["id"], now(), me["id"]))
            n += 1
        msg += " %d network%s banned too." % (n, "" if n == 1 else "s") if n else " No networks were recorded for them, so only the account is banned."
        if skipped:
            msg += " (One was the network you're on now, so it was left out.)"
    return self.view_admin(req, msg)


def admin_invites(self, req, out, c):
    invs = self.store.q("SELECT i.*, u.username FROM invites i LEFT JOIN users u ON u.id=i.created_by WHERE used_by IS NULL ORDER BY created DESC")
    host = req.h.headers.get("Host") or "plus.gplexextended.com"
    scheme = "https" if req.secure else "http"
    out.append('<div class="card"><h2>Invites</h2><form action="/admin/invite" method="post">%s<input class="t" type="text" name="note" '
               'maxlength="80" placeholder="Who is it for? (only admins see this)" style="width:300px"> '
               '<label class="small">People who can use it: <input class="t" type="number" name="uses" value="1" min="1" max="%d" '
               'style="width:70px"></label> '
               '<input class="btn" type="submit" value="Make an invite link"></form>'
               '<p class="muted small" style="margin:6px 0 0">1 makes a link for one person. A bigger number makes a link several people '
               'can join with (for example one you post in a group chat); it stops working after that many have joined, or when you cancel it.</p>'
               % (c, P.MAX_INVITE_USES))
    if invs:
        out.append('<table class="list"><tr><th style="width:150px">For</th><th>Link (send it privately)</th>'
                   '<th style="width:120px">Used</th><th style="width:70px"></th></tr>')
        for i in invs:
            mx = max(1, i["max_uses"])
            out.append('<tr><td>%s</td><td><input class="t" type="text" readonly value="%s://%s/join?invite=%s"></td>'
                       '<td class="small">%s</td>'
                       '<td><form class="inl" action="/admin/revoke" method="post">%s<input type="hidden" name="code" value="%s">'
                       '<input class="btn grey" type="submit" value="Cancel"></form></td></tr>' % (
                           esc(i["note"]) or '<span class="muted">-</span>', scheme, esc(host), esc(i["code"]),
                           "once" if mx == 1 else "%d of %d people" % (i["uses"], mx), c, esc(i["code"])))
        out.append("</table>")
    out.append("</div>")



def do_admin(self, req, rest):
    me = req.user
    admin = is_admin(me)
    if rest in ("invite", "revoke") and not admin:
        return Reply.redirect("/admin")

    def resolve(rid, note):
        if rid and str(rid).isdigit():
            self.store.run("UPDATE reports SET status='resolved', resolved_by=?, note=? WHERE id=?", (req.user["id"], note, int(rid)))
    if rest == "invite":
        code = secrets.token_urlsafe(12)
        try:
            n = int((req.form.get("uses") or "1").strip())
        except ValueError:
            n = 1
        n = min(max(n, 1), P.MAX_INVITE_USES)
        self.store.run("INSERT INTO invites (code, created_by, created, note, max_uses) VALUES (?, ?, ?, ?, ?)",
                       (code, req.user["id"], now(), (req.form.get("note") or "").strip()[:80], n))
        return self.view_admin(req, "Invite made. Copy its link from the list and send it privately." if n == 1 else
                               "Invite made for up to %d people. Copy its link from the list; it stops working after %d have joined." % (n, n))
    if rest == "revoke":
        self.store.run("DELETE FROM invites WHERE code=? AND used_by IS NULL", (req.form.get("code", ""),))
        return Reply.redirect("/admin")
    if rest == "resolve":
        resolve(req.form.get("report"), "dismissed")
        return Reply.redirect("/admin")
    if rest == "remove":
        kind, tid = req.form.get("kind"), req.form.get("id", "")
        if kind in ("post", "comment") and tid.isdigit():
            table = "posts" if kind == "post" else "comments"
            row = self.store.one("SELECT author_id FROM %s WHERE id=?" % table, (int(tid),))
            author = self.store.one("SELECT * FROM users WHERE id=?", (row["author_id"],)) if row else None
            if not row or not can_moderate(me, author):
                return self.view_admin(req, "Only an admin can remove what a moderator or admin posted.")
            self.store.run("UPDATE %s SET removed=1 WHERE id=?" % table, (int(tid),))
        resolve(req.form.get("report"), "removed")
        return Reply.redirect("/admin")
    if rest == "user":
        tid = req.form.get("id", "")
        do = req.form.get("do")
        if not tid.isdigit():
            return Reply.redirect("/admin")
        uid = int(tid)
        target = self.store.one("SELECT * FROM users WHERE id=?", (uid,))
        if not target:
            return Reply.redirect("/admin")
        if do in ("reset", "admin", "mod", "member", "ban", "banip", "unban") and not admin:
            return Reply.redirect("/admin")
        if do == "reset":
            tok = secrets.token_urlsafe(24)
            self.store.run("INSERT INTO resets (token, user_id, created) VALUES (?, ?, ?)", (P.sha(tok), uid, now()))
            host = req.h.headers.get("Host") or "plus.gplexextended.com"
            link = "%s://%s/reset?token=%s" % ("https" if req.secure else "http", host, tok)
            return self.view_admin(req, 'Password link (works once, for a week; send it to them privately): '
                                        '<input class="t" type="text" readonly value="%s" style="width:420px">' % esc(link))
        if uid == me["id"]:
            return Reply.redirect("/admin")
        if do in ("suspend", "unsuspend") and not can_moderate(me, target):
            return self.view_admin(req, "Moderators can suspend members, but not other moderators or admins.")
        if do in ("suspend", "unsuspend") and target["status"] == "banned":
            return self.view_admin(req, "That account is banned; only an admin can lift the ban.")
        if do in ("ban", "banip", "unban"):
            if not can_moderate(me, target):
                return Reply.redirect("/admin")
            return admin_ban(self, req, target, do, resolve)
        if do == "suspend":
            self.store.run("UPDATE users SET status='suspended' WHERE id=?", (uid,))
            self.store.run("DELETE FROM sessions WHERE user_id=?", (uid,))
            resolve(req.form.get("report"), "author suspended")
        elif do == "unsuspend":
            self.store.run("UPDATE users SET status='active' WHERE id=?", (uid,))
        elif do in ("admin", "mod", "member"):
            self.store.run("UPDATE users SET role=? WHERE id=?", (do, uid))
        return Reply.redirect("/admin")
    return Reply.redirect("/admin")


# ---- rules, terms, privacy ----
STATIC = {
    "rules": ("Community rules", """<h2>Community rules</h2>
<p>Gplex+ is a small, friendly place. To keep it that way:</p>
<ul>
<li><b>Be kind.</b> No harassment, bullying, threats or hate against anyone for who they are. Swear words and slurs are filtered out:
posts, comments and names that use them (however they're spelled) aren't accepted.</li>
<li><b>Nothing illegal.</b> No content that breaks the law, and absolutely nothing sexualising minors. That is reported to the authorities.</li>
<li><b>No sexual or gory content.</b> Keep it suitable for everyone.</li>
<li><b>No spam or scams.</b> No advertising floods, phishing or malware links. New members can share links once they've been on
Gplex+ for 2 hours.</li>
<li><b>Be yourself.</b> Don't pretend to be another person.</li>
<li><b>Respect privacy.</b> Don't post other people's private information without their permission.</li>
<li><b>Share what you have the right to share.</b> Don't post other people's copyrighted work without permission.</li>
</ul>
<p>Use <b>Report</b> on any post, comment or profile that breaks these rules. Moderators and admins can remove content and suspend accounts.</p>"""),
    "terms": ("Terms", """<h2>Terms</h2>
<p>Gplex+ is a free, invite-only community run by volunteers as part of the Gplex Extended fan project. By using it you agree to the
<a href="/rules">community rules</a>. You must be 13 or older (16 or older in the EU).</p>
<p>You keep the rights to what you post. You give Gplex+ permission to store it and show it to the people you share it with, for as
long as you keep it here. Delete a post, or your whole account from Settings, and it is gone.</p>
<p>Moderators and admins may remove content or suspend accounts that break the rules, and admins may ban accounts, and the networks
they're used from, for good. Gplex+ is offered as it is, without guarantees; it may change
or close. It is not made by, affiliated with or endorsed by Google.</p>
<p>Copyright complaints and other questions: {contact}.</p>"""),
    "privacy": ("Privacy", """<h2>Privacy</h2>
<p><b>What is kept:</b> your username, name, password (scrambled, so nobody can read it), the profile text you add, your
posts, comments, +1s and circles, and your notifications. Reports you send are kept for the admins.</p>
<p><b>Pictures:</b> Gplex+ is text only: it doesn't take photos or other pictures.</p>
<p><b>Who sees what:</b> posts shared publicly are visible to every member; posts shared with circles only to the people in those
circles. Gplex+ is members-only: nothing is visible to people who aren't signed in. Moderators and admins can see reported content.</p>
<p><b>Network addresses:</b> so that a banned person can't simply come back, Gplex+ keeps a scrambled, one-way form of the
internet addresses you use it from (never the addresses themselves) for six months. They are used only to enforce bans.</p>
<p><b>Cookies:</b> one cookie keeps you signed in, and one protects the forms. No tracking, analytics or ads, and nothing is shared
with or sold to anyone.</p>
<p><b>Gplex Extended:</b> Gplex+ itself loads nothing from other sites. If you use the Gplex Extended script or add-on, it can show
Gplex+ the way Google+ looked in the year you picked; that look may load fonts from Google Fonts (fonts.googleapis.com and
fonts.gstatic.com), which then see your IP address, as with any site that uses them.</p>
<p><b>Your choices:</b> download your data or delete your account in <a href="/settings">Settings</a>; deleting removes your profile,
posts, comments, +1s and circles.</p>
<p>Questions: {contact}.</p>"""),
    "about": ("About", """<h2>About Gplex+</h2>
<p>Gplex+ is a small invite-only community in the spirit of Google+ (2011-2013): a stream, circles to choose who sees what, +1s and
comments. It is part of the <a href="https://gplexextended.com/">Gplex Extended</a> fan project, and is not made by, affiliated with
or endorsed by Google.</p>"""),
}


def view_static(self, req, key):
    title, text = STATIC[key]
    # who to write to: the site's own contact (GPLEX_PLUS_CONTACT, or plus.CONTACT set by the server)
    text = text.replace("{contact}", esc(P.CONTACT) if P.CONTACT else "write to the people who run this site")
    body = '<div class="card">%s</div>' % text
    if req.user:
        return self.page(req, title, body)
    return self.page(req, title, '<div class="welcome" style="width:640px">%s</div>' % body, bare=True)
