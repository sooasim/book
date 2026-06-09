import unittest

import auth


class TestAuth(unittest.TestCase):
    def test_round_trip(self):
        token = auth.make_token("alice")
        payload = auth.verify_token(token)
        self.assertEqual(payload["sub"], "alice")
        self.assertEqual(auth.user_from_token(token), "alice")

    def test_payload_claims(self):
        token = auth.make_token("bob", now=1000, exp_seconds=60)
        payload = auth.verify_token(token, now=1000)
        self.assertEqual(payload["sub"], "bob")
        self.assertEqual(payload["iat"], 1000)
        self.assertEqual(payload["exp"], 1060)

    def test_tamper_payload(self):
        token = auth.make_token("alice")
        header, payload, signature = token.split(".")
        # flip one character of the payload segment
        ch = "B" if payload[0] != "B" else "C"
        tampered = f"{header}.{ch}{payload[1:]}.{signature}"
        with self.assertRaises(ValueError):
            auth.verify_token(tampered)

    def test_wrong_secret(self):
        token = auth.make_token("alice", secret="right-secret")
        with self.assertRaises(ValueError):
            auth.verify_token(token, secret="wrong-secret")

    def test_expired(self):
        token = auth.make_token("alice", now=1000, exp_seconds=10)
        with self.assertRaises(ValueError) as ctx:
            auth.verify_token(token, now=2000)
        self.assertEqual(str(ctx.exception), "expired")

    def test_not_expired_at_boundary(self):
        token = auth.make_token("alice", now=1000, exp_seconds=10)
        # exp == 1010; at now=1005 it is still valid
        payload = auth.verify_token(token, now=1005)
        self.assertEqual(payload["sub"], "alice")

    def test_malformed_not_three_parts(self):
        with self.assertRaises(ValueError):
            auth.verify_token("only.two")
        with self.assertRaises(ValueError):
            auth.verify_token("a.b.c.d")
        with self.assertRaises(ValueError):
            auth.verify_token("nodots")

    def test_parse_bearer(self):
        self.assertEqual(auth.parse_bearer("Bearer abc"), "abc")
        self.assertIsNone(auth.parse_bearer(None))
        self.assertIsNone(auth.parse_bearer("abc"))

    def test_b64url_round_trip_no_padding(self):
        for raw in (b"", b"a", b"ab", b"abc", b"abcd", b"\x00\xff\x10"):
            enc = auth.b64url_encode(raw)
            self.assertNotIn("=", enc)
            self.assertEqual(auth.b64url_decode(enc), raw)


if __name__ == "__main__":
    unittest.main()
