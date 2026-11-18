import asyncio
import hashlib
import json
import secrets
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

import app as activity_app


async def make_request(method, target, payload=None, cookie=None):
    parsed_target = urlsplit(target)
    body = json.dumps(payload).encode("utf-8") if payload is not None else b""
    headers = [(b"host", b"testserver")]
    if payload is not None:
        headers.append((b"content-type", b"application/json"))
    if cookie is not None:
        headers.append((b"cookie", cookie.encode("latin-1")))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": unquote(parsed_target.path),
        "raw_path": parsed_target.path.encode("ascii"),
        "query_string": parsed_target.query.encode("ascii"),
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    request_sent = False
    response_messages = []

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        response_messages.append(message)

    await activity_app.app(scope, receive, send)
    response_start = next(
        message
        for message in response_messages
        if message["type"] == "http.response.start"
    )
    response_body = b"".join(
        message.get("body", b"")
        for message in response_messages
        if message["type"] == "http.response.body"
    )
    return (
        response_start["status"],
        dict(response_start["headers"]),
        json.loads(response_body) if response_body else None,
    )


class AdminModeTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.teachers_file = Path(self.temporary_directory.name) / "teachers.json"
        salt = secrets.token_bytes(16)
        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            b"correct-password",
            salt,
            activity_app.PASSWORD_HASH_ITERATIONS,
        )
        self.teachers_file.write_text(
            json.dumps(
                {
                    "teachers": [
                        {
                            "username": "teacher1",
                            "salt": salt.hex(),
                            "password_hash": password_hash.hex(),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.teachers_file_patch = patch.object(
            activity_app, "TEACHERS_FILE", self.teachers_file
        )
        self.teachers_file_patch.start()
        self.original_activities = json.loads(json.dumps(activity_app.activities))
        self.original_sessions = activity_app.teacher_sessions.copy()
        activity_app.teacher_sessions.clear()

    def tearDown(self):
        activity_app.activities.clear()
        activity_app.activities.update(self.original_activities)
        activity_app.teacher_sessions.clear()
        activity_app.teacher_sessions.update(self.original_sessions)
        self.teachers_file_patch.stop()
        self.temporary_directory.cleanup()

    def request(self, method, target, payload=None, cookie=None):
        return asyncio.run(make_request(method, target, payload, cookie))

    def test_students_can_view_but_cannot_manage_registrations(self):
        email = "student@example.edu"
        status, _, activities = self.request("GET", "/activities")
        self.assertEqual(status, 200)
        self.assertIn("Chess Club", activities)

        status, _, _ = self.request(
            "POST",
            f"/activities/Chess%20Club/signup?email={email}",
            payload={},
        )
        self.assertEqual(status, 401)
        self.assertNotIn(email, activity_app.activities["Chess Club"]["participants"])

        status, _, _ = self.request(
            "DELETE",
            f"/activities/Chess%20Club/unregister?email=michael%40mergington.edu",
        )
        self.assertEqual(status, 401)
        self.assertIn(
            "michael@mergington.edu",
            activity_app.activities["Chess Club"]["participants"],
        )

    def test_teacher_login_allows_registration_until_logout(self):
        status, headers, _ = self.request(
            "POST",
            "/auth/login",
            {"username": "teacher1", "password": "correct-password"},
        )
        self.assertEqual(status, 200)
        set_cookie = headers[b"set-cookie"].decode("latin-1")
        cookie = set_cookie.split(";", 1)[0]
        self.assertIn("httponly", set_cookie.lower())

        status, _, session = self.request("GET", "/auth/session", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertTrue(session["is_teacher"])
        self.assertEqual(session["username"], "teacher1")

        email = "student@example.edu"
        status, _, _ = self.request(
            "POST",
            f"/activities/Chess%20Club/signup?email={email}",
            payload={},
            cookie=cookie,
        )
        self.assertEqual(status, 200)
        self.assertIn(email, activity_app.activities["Chess Club"]["participants"])

        status, _, _ = self.request(
            "DELETE",
            f"/activities/Chess%20Club/unregister?email={email}",
            cookie=cookie,
        )
        self.assertEqual(status, 200)
        self.assertNotIn(email, activity_app.activities["Chess Club"]["participants"])

        status, _, _ = self.request("POST", "/auth/logout", cookie=cookie)
        self.assertEqual(status, 200)
        status, _, session = self.request("GET", "/auth/session", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertFalse(session["is_teacher"])

        status, _, _ = self.request(
            "POST",
            f"/activities/Chess%20Club/signup?email={email}",
            payload={},
            cookie=cookie,
        )
        self.assertEqual(status, 401)

    def test_invalid_teacher_credentials_are_rejected(self):
        status, _, response = self.request(
            "POST",
            "/auth/login",
            {"username": "teacher1", "password": "wrong-password"},
        )
        self.assertEqual(status, 401)
        self.assertEqual(response["detail"], "Invalid username or password")


if __name__ == "__main__":
    unittest.main()
