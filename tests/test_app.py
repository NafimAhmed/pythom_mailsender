"""Microsoft Graph-only Flask API tests. No real mail is sent."""
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from app import app, load_project_env
from graph_mail import GraphMailError


class MailSenderTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {"MAIL_API_KEY": "local-test-api-key"})
        self.env_patch.start()
        self.client = app.test_client()
        self.headers = {"X-API-Key": "local-test-api-key"}

    def tearDown(self):
        self.env_patch.stop()

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])

    def test_reads_explicit_dotenv_path_and_overrides_stale_values(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / ".env").write_text(
                "MAIL_API_KEY=key-from-project-env\n", encoding="utf-8"
            )
            with patch("app.BASE_DIR", Path(folder)), patch.dict(
                os.environ, {"MAIL_API_KEY": "stale-value"}
            ):
                load_project_env()
                self.assertEqual(os.environ["MAIL_API_KEY"], "key-from-project-env")

    def test_requires_api_key(self):
        response = self.client.post("/api/v1/mail/send", json={"to": "a@example.com"})
        self.assertEqual(response.status_code, 401)

    def test_wrong_api_key(self):
        response = self.client.post(
            "/api/v1/mail/send",
            headers={"X-API-Key": "wrong"},
            json={"to": "a@example.com", "subject": "Hello", "body": "Text"}
        )
        self.assertEqual(response.status_code, 401)

    def test_missing_key_configuration(self):
        with patch.dict(os.environ, {"MAIL_API_KEY": ""}):
            response = self.client.post("/api/v1/mail/send", headers=self.headers, json={})
            self.assertEqual(response.status_code, 503)

    def test_rejects_invalid_email(self):
        response = self.client.post(
            "/api/v1/mail/send", headers=self.headers,
            json={"to": "invalid-address", "subject": "Hello", "body": "Text"}
        )
        self.assertEqual(response.status_code, 400)

    def test_rejects_injected_subject(self):
        response = self.client.post(
            "/api/v1/mail/send", headers=self.headers,
            json={"to": "a@example.com", "subject": "Hi\r\nBcc:bad@example.com", "body": "Text"}
        )
        self.assertEqual(response.status_code, 400)

    @patch("app.send_via_graph")
    def test_graph_mail_accepted(self, send):
        response = self.client.post(
            "/api/v1/mail/send", headers=self.headers,
            json={"to": ["a@example.com"], "cc": ["b@example.com"],
                  "bcc": ["c@example.com"], "subject": "Hi", "body": "Text",
                  "html": "<p>HTML</p>"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["recipient_count"], 3)
        send.assert_called_once()
        data = send.call_args.args[0]
        self.assertEqual(data["bcc"], ["c@example.com"])

    @patch("app.send_via_graph", side_effect=GraphMailError("sendMail", 403))
    def test_graph_forbidden(self, send):
        response = self.client.post(
            "/api/v1/mail/send", headers=self.headers,
            json={"to": "a@example.com", "subject": "Hi", "body": "Text"}
        )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json["upstream_status"], 403)

    @patch("app.send_via_graph", side_effect=ValueError("bad env"))
    def test_graph_not_configured(self, send):
        response = self.client.post(
            "/api/v1/mail/send", headers=self.headers,
            json={"to": "a@example.com", "subject": "Hi", "body": "Text"}
        )
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
