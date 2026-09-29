from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


class ReferralTests(TestCase):
    def register(self, name, code=None):
        payload = {"username": name, "email": f"{name}@example.com", "password": "Str0ng-pass!"}
        if code:
            payload["referral_code"] = code
        return self.client.post("/api/auth/register/", payload, content_type="application/json")

    def setUp(self):
        cache.clear()  # reset throttle counters
        self.client = APIClient()

    def test_registration_without_code_creates_root(self):
        r = self.register("root")
        self.assertEqual(r.status_code, 201)
        user = User.objects.get(username="root")
        self.assertIsNone(user.parent)
        self.assertEqual(len(user.referral_code), 8)
        self.assertIn("token", r.json())

    def test_invalid_referral_code(self):
        r = self.register("x", code="NOPE1234")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "invalid_referral_code")
        self.assertFalse(User.objects.filter(username="x").exists())

    def test_placement_fills_left_then_right_then_bfs(self):
        root = User.objects.get(pk=self.register("root").json()["user"]["id"])
        code = root.referral_code
        names = ["a", "b", "c", "d", "e", "f", "g"]
        for n in names:
            self.assertEqual(self.register(n, code).status_code, 201)
        u = {n: User.objects.get(username=n) for n in names}
        # Level 1
        self.assertEqual((u["a"].parent, u["a"].position), (root, "left"))
        self.assertEqual((u["b"].parent, u["b"].position), (root, "right"))
        # Level 2, filled left to right (BFS)
        self.assertEqual((u["c"].parent, u["c"].position), (u["a"], "left"))
        self.assertEqual((u["d"].parent, u["d"].position), (u["a"], "right"))
        self.assertEqual((u["e"].parent, u["e"].position), (u["b"], "left"))
        self.assertEqual((u["f"].parent, u["f"].position), (u["b"], "right"))
        # Level 3 begins under c
        self.assertEqual((u["g"].parent, u["g"].position), (u["c"], "left"))
        # Referrer is always the code owner, regardless of placement
        self.assertEqual(u["g"].referrer, root)

    def test_referring_a_non_root_places_under_that_user(self):
        root = User.objects.get(pk=self.register("root").json()["user"]["id"])
        self.register("a", root.referral_code)
        a = User.objects.get(username="a")
        self.register("b", a.referral_code)
        b = User.objects.get(username="b")
        self.assertEqual((b.parent, b.position), (a, "left"))

    def test_tree_root_and_stats_endpoints(self):
        root = User.objects.get(pk=self.register("root").json()["user"]["id"])
        for n in ["a", "b", "c", "d"]:
            self.register(n, root.referral_code)
        token = self.register("viewer").json()["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")

        stats = self.client.get(f"/api/referrals/{root.pk}/stats/").json()
        # a(left) has c,d beneath it; b(right) has nothing
        self.assertEqual(
            (stats["left_count"], stats["right_count"], stats["total_team"]), (3, 1, 4)
        )
        tree = self.client.get(f"/api/referrals/{root.pk}/tree/").json()
        self.assertEqual(tree["left"]["username"], "a")
        self.assertEqual(tree["left"]["left"]["username"], "c")
        self.assertEqual(tree["right"]["username"], "b")
        shallow = self.client.get(f"/api/referrals/{root.pk}/tree/?depth=0").json()
        self.assertIsNone(shallow["left"])

        d = User.objects.get(username="d")
        self.assertEqual(self.client.get(f"/api/referrals/{d.pk}/root/").json()["id"], root.pk)

    def test_unknown_user_and_bad_depth(self):
        token = self.register("viewer").json()["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(self.client.get("/api/referrals/9999/tree/").status_code, 404)
        self.assertEqual(self.client.get("/api/referrals/9999/root/").status_code, 404)
        self.assertEqual(self.client.get("/api/referrals/9999/stats/").status_code, 404)
        me = User.objects.get(username="viewer")
        self.assertEqual(self.client.get(f"/api/referrals/{me.pk}/tree/?depth=abc").status_code, 400)

    def test_referral_endpoints_require_auth(self):
        self.assertEqual(self.client.get("/api/referrals/1/tree/").status_code, 401)


class AuthTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_login_logout(self):
        c = APIClient()
        User.objects.create_user("u", "u@example.com", "Str0ng-pass!")
        bad = c.post("/api/auth/login/", {"username": "u", "password": "nope"}, format="json")
        self.assertEqual(bad.status_code, 400)
        ok = c.post("/api/auth/login/", {"username": "u", "password": "Str0ng-pass!"}, format="json")
        self.assertEqual(ok.status_code, 200)
        c.credentials(HTTP_AUTHORIZATION=f"Token {ok.json()['token']}")
        self.assertEqual(c.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(c.get("/api/events/").status_code, 401)

    def test_duplicate_email_and_weak_password_rejected(self):
        c = APIClient()
        User.objects.create_user("u", "u@example.com", "Str0ng-pass!")
        r = c.post("/api/auth/register/", {"username": "n", "email": "U@example.com", "password": "Str0ng-pass!"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = c.post("/api/auth/register/", {"username": "n", "email": "n@example.com", "password": "123"}, format="json")
        self.assertEqual(r.status_code, 400)
