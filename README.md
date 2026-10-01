# Gplex+

A small, invite-only social network in the style of Google+ (2011–2013): a stream, circles to choose who
sees what, +1s, comments, notifications and profiles. It is the community of the
[Gplex Extended](https://gplexextended.com/) fan project, running at plus.gplexextended.com.

Gplex+ is a fan project. It is not made by, affiliated with or endorsed by Google.

- **Python 3.8+, standard library only.** No packages to install, no JavaScript, no build step.
- **Plain HTML 4.01 and forms**, so it works in old browsers too.
- **Text only.** No photos or other pictures can be uploaded; everyone shows as a coloured initial.

## Running it

```
python3 run.py
```

Then open http://localhost:8080/. On the first start, with no members yet, it prints a link for the first
account (also saved in `data/plus/first-invite.txt`). That account is the admin; it makes invite links for
everyone else on the Admin page.

Options (`python3 run.py --help`):

| Option | |
|---|---|
| `--port 8080` | the HTTP port |
| `--https-port 443 --cert fullchain.pem --key privkey.pem` | also serve HTTPS; plain HTTP then redirects to it |
| `--data-dir ./data` | where the database and keys live |
| `--contact you@example.com` | the email shown on the terms and privacy pages (or `GPLEX_PLUS_CONTACT`) |

The live site runs Gplex+ inside the Gplex Extended website's own server instead, which hands it every
request for `plus.<domain>`; `run.py` is the same thing on its own.

## Tests

```
python3 -m unittest discover tests
```

## The code

| File | What's in it |
|---|---|
| `plus.py` | the database (SQLite), passwords, sessions and CSRF, IP hashing, request parsing, dispatch, response headers |
| `plus_views.py` | every page and form: stream, posts, comments, +1s, circles, profiles, notifications, settings, reports, Admin/Moderate, the rules/terms/privacy pages, and the CSS |
| `plus_filter.py` | the word filter, the link detector, and the look-alike name checks |
| `run.py` | a standalone web server around `plus.App` |
| `tests/` | the tests |

The data folder holds `plus/plus.db` (everything), `plus/ip-key` (the key for IP hashes; keep it with the
database) and `plus/media/` (only photos from before Gplex+ became text only; never served).

## How it stays safe

- **Accounts:** passwords are hashed with scrypt (PBKDF2 if scrypt isn't available). They must be at least
  10 characters and not built on the username, name or a common password; anyone signing in with an older
  weak one must change it before doing anything else. Five wrong passwords for an account in an hour, or
  twenty from one network, stop sign-ins for an hour.
- **Sessions:** a random token in an HttpOnly, SameSite=Lax cookie (Secure over HTTPS); only its SHA-256 is
  stored. Settings lists where an account is signed in, with "Sign out everywhere else".
- **Forms:** every POST needs the session's CSRF token, and the Origin/Referer must be this site.
- **Pages:** `Content-Security-Policy` with `script-src 'none'`; everything members write is escaped.
- **Identity:** display names can't pass for another member's name or username (look-alike letters,
  accents, 0-for-O, spacing and invisible characters are all seen through), and only staff may use words
  like admin or moderator. Posts show each author's unique @username and a badge for staff.
- **Moderation:** members report posts, comments and profiles. Moderators answer reports and suspend
  members; admins can also ban accounts permanently, and the networks they used. IP addresses are never
  stored, only a keyed one-way hash of them.
- **Content:** a word filter for swear words, slurs and hateful phrases (with their usual disguises);
  new members can't share links for their first two hours.

## Contributing

Bug reports and pull requests are welcome. Please keep to what's there already:

- standard library only, no JavaScript on the pages, HTML that old browsers can show;
- escape everything that comes from members (`esc()`), and keep every form behind the CSRF check;
- run the tests before sending a change, and add one for what you fixed.

**Security problems: please don't open a public issue.** See [SECURITY.md](SECURITY.md).

The word lists in `plus_filter.py` are stored ROT13-encoded so the file isn't a wall of slurs; the note at
its top explains how to add words.

## License

MIT; see [LICENSE](LICENSE).
