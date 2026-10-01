"""Tests for Gplex+: python3 -m unittest discover tests   (from the project folder)"""
import http.cookiejar
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import plus  # noqa: E402
import plus_filter as F  # noqa: E402
import run  # noqa: E402

ORDINARY = ["Hello everyone!", "I passed the class", "Scunthorpe United", "cocktail party at the peacock bar", "the assassin's creed",
            "bass guitar", "I assume you assessed the assets", "Dickens novel", "shiitake mushrooms", "therapist appointment",
            "Niger river", "as you wish", "this hit song", "Sussex", "Matsushita", "Pakistan", "raccoon", "bitcoin", "Wankel engine",
            "C++ and C# code", "50% off", "a b c d e", "Mississippi", "the classic cassette"]


class FilterTests(unittest.TestCase):
    def disguises(self, w):
        leet = {"a": "4", "e": "3", "i": "1", "o": "0", "s": "$", "t": "7"}
        cyr = {"a": "а", "e": "е", "o": "о", "c": "с", "p": "р", "x": "х"}
        mid = len(w) // 2
        out = [w, w.upper(), w.capitalize() + "!!!", ".".join(w), " ".join(w), w[:1] + "." + w[1:],
               "".join(leet.get(c, c) for c in w), "".join(cyr.get(c, c) for c in w), w[:mid] + "​" + w[mid:],
               "".join(chr(ord(c) + 0xFEE0) for c in w), w[:mid] + w[mid] * 4 + w[mid + 1:], "this is " + w + " really"]
        v = [i for i, c in enumerate(w) if c in "aeiou"]
        if v:
            out.append(w[:v[0]] + "*" + w[v[0] + 1:])
        return out

    def test_listed_words_and_disguises(self):
        # the words come from the (ROT13) lists themselves, so none are written out here
        for w in [x for x in F._ANY if len(x) > 3] + list(F._WORD):
            for d in self.disguises(w):
                self.assertTrue(F.check(d), "missed a disguise of a listed word (ROT13: %s)" % F.codecs.encode(w, "rot13"))

    def test_ordinary_text(self):
        for t in ORDINARY:
            self.assertFalse(F.check(t), t)

    def test_links(self):
        for t in ["https://example.com", "www.example.org", "bit.ly/abc", "example dot com", "example(.)com", "discord.gg/x", "t.me/x"]:
            self.assertTrue(F.has_link(t), t)
        for t in ["pi is 3.14", "version 7.2.13", "U.S. history", "node.js is neat", "the dot com bubble", "Wait... what?"]:
            self.assertFalse(F.has_link(t), t)

    def test_lookalike_names(self):
        me = F.skeleton("Ziptino9098")
        for fake in ["ziptin09098", "ZIPTINO 9098", "Zíptino9098", "Zіptіno9098", "Zipptino9098", "Zip​tino9098"]:
            self.assertEqual(F.skeleton(fake), me, fake)
        self.assertNotEqual(F.skeleton("Ziptino9097"), me)
        self.assertTrue(F.reserved("Gplex Admin"))
        self.assertFalse(F.reserved("Badminton fan"))

    def test_passwords(self):
        self.assertIsNotNone(plus.password_problem("Ziptino9098!", "ziptino9098", "Ziptino9098"))
        self.assertIsNotNone(plus.password_problem("password123", "ada", "Ada"))
        self.assertIsNotNone(plus.password_problem("short", "ada", "Ada"))
        self.assertIsNone(plus.password_problem("maple-orbit-quilt-44", "ada", "Ada Lovelace"))


class SiteTests(unittest.TestCase):
    """A real server on a free port: the first (admin) account joins and posts."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        run.APP = plus.App(cls.dir, log=lambda m: None)
        cls.httpd = run.Server(("127.0.0.1", 0), run.Handler)
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_join_and_post(self):
        jar = http.cookiejar.CookieJar()
        web = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        code = re.search(r"invite=([\w-]+)", open(os.path.join(self.dir, "plus", "first-invite.txt")).read()).group(1)
        page = web.open(self.base + "/join?invite=" + code).read().decode()
        csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
        form = {"csrf": csrf, "invite": code, "name": "Test Admin", "username": "tadmin", "password": "maple-orbit-quilt-44",
                "password2": "maple-orbit-quilt-44", "age": "1", "rules": "1"}
        web.open(self.base + "/join", urllib.parse.urlencode(form).encode()).read()
        home = web.open(self.base + "/").read().decode()
        self.assertIn("Test Admin", home)
        csrf = re.search(r'name="csrf" value="([^"]+)"', home).group(1)
        web.open(self.base + "/post", urllib.parse.urlencode({"csrf": csrf, "body": "Hello, *Gplex+*", "vis": "public"}).encode()).read()
        self.assertIn("<b>Gplex+</b>", web.open(self.base + "/").read().decode())
        # a form without the right token is refused
        with self.assertRaises(urllib.error.HTTPError) as e:
            web.open(self.base + "/post", urllib.parse.urlencode({"csrf": "wrong", "body": "forged", "vis": "public"}).encode())
        self.assertEqual(e.exception.code, 403)

    def test_members_only(self):
        r = urllib.request.urlopen(self.base + "/explore")
        self.assertTrue(r.geturl().endswith("/signin?next=/explore"))


if __name__ == "__main__":
    unittest.main()
