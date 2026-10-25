"""API tests; SMTP is mocked so no real email is sent."""
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from app import app, load_project_env
from graph_mail import GraphMailError


class MailSenderTests(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {
            "MAIL_API_KEY": "local-test-api-key",
            "MAIL_PROVIDER": "smtp",
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_SECURITY": "starttls",
            "SMTP_USER": "sender@example.com",
            "SMTP_PASSWORD": "dummy-password",
            "SMTP_FROM": "sender@example.com",
        })
        self.env_patch.start()
        self.client = app.test_client()
        self.headers = {"X-API-Key": "local-test-api-key"}

    def tearDown(self):
        self.env_patch.stop()

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])

    def test_env_file_is_loaded_from_project_directory_and_overrides_stale_key(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / ".env").write_text(
                "MAIL_API_KEY=key-from-project-env\n", encoding="utf-8"
            )
            with patch("app.BASE_DIR", Path(folder)), patch.dict(
                os.environ, {"MAIL_API_KEY": "stale-shell-key"}
            ):
                load_project_env()
                self.assertEqual(os.environ["MAIL_API_KEY"], "key-from-project-env")

    def test_wrong_api_key_returns_401(self):
        response = self.client.post(
            "/api/v1/mail/send",
            headers={"X-API-Key": "not-the-right-key"},
            json={"to": "a@example.com", "subject": "Hi", "body": "Hello"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json["error"], "Unauthorized")

    def test_missing_server_api_key_returns_503(self):
        with patch.dict(os.environ, {"MAIL_API_KEY": ""}):
            response = self.client.post(
                "/api/v1/mail/send", headers=self.headers,
                json={"to": "a@example.com", "subject": "Hi", "body": "Hello"},
            )
            self.assertEqual(response.status_code, 503)

    def test_requires_api_key(self):
        response = self.client.post("/api/v1/mail/send", json={"to": "a@example.com"})
        self.assertEqual(response.status_code, 401)

    def test_validates_json(self):
        response = self.client.post("/api/v1/mail/send", headers=self.headers,
                                    json={"to": "invalid-address", "subject": "X", "body": "Y"})
        self.assertEqual(response.status_code, 400)

    def test_rejects_newline_subject(self):
        response = self.client.post("/api/v1/mail/send", headers=self.headers,
                                    json={"to": "a@example.com", "subject": "X\r\nBcc: bad@example.com", "body": "Y"})
        self.assertEqual(response.status_code, 400)

    @patch("app.send_via_graph")
    def test_graph_provider_keeps_existing_endpoint(self, mocked_sender):
        with patch.dict(os.environ, {"MAIL_PROVIDER": "graph"}):
            data = {"to": ["a@example.com"], "cc": ["b@example.com"],
                    "subject": "Graph", "body": "Hello", "html": "<h1>Hello</h1>"}
            response = self.client.post("/api/v1/mail/send", headers=self.headers, json=data)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["recipient_count"], 2)
            mocked_sender.assert_called_once()

    @patch("app.send_via_graph", side_effect=GraphMailError("Graph sendMail endpoint", 403))
    def test_graph_permission_failure(self, mocked_sender):
        with patch.dict(os.environ, {"MAIL_PROVIDER": "graph"}):
            data = {"to": "a@example.com", "subject": "Graph", "body": "Hello"}
            response = self.client.post("/api/v1/mail/send", headers=self.headers, json=data)
            self.assertEqual(response.status_code, 502)
            self.assertEqual(response.json["upstream_status"], 403)

    @patch("app.smtplib.SMTP")
    def test_send_text_html_cc_bcc(self, smtp):
        smtp_instance = MagicMock()
        smtp.return_value.__enter__.return_value = smtp_instance
        smtp_instance.send_message.return_value = {}
        data = {"to": ["a@example.com"], "cc": ["b@example.com"],
                "bcc": "secret@example.com", "subject": "Hello",
                "body": "Text", "html": "<strong>HTML</strong>"}
        response = self.client.post("/api/v1/mail/send", headers=self.headers, json=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["recipient_count"], 3)
        smtp_instance.starttls.assert_called_once()
        smtp_instance.login.assert_called_once_with("sender@example.com", "dummy-password")
        args, kwargs = smtp_instance.send_message.call_args
        self.assertIn("secret@example.com", kwargs["to_addrs"])
        self.assertNotIn("Bcc", args[0])
        self.assertIn("Cc", args[0])
        self.assertTrue(args[0].is_multipart())

    @patch("app.smtplib.SMTP_SSL")
    def test_ssl(self, smtp_ssl):
        os.environ["SMTP_SECURITY"] = "ssl"
        os.environ["SMTP_PORT"] = "465"
        smtp_ssl.return_value.__enter__.return_value.send_message.return_value = {}
        response = self.client.post("/api/v1/mail/send", headers=self.headers,
                                    json={"to": "a@example.com", "subject": "Hi", "body": "Message"})
        self.assertEqual(response.status_code, 200)
        smtp_ssl.assert_called_once()


if __name__ == "__main__":
    unittest.main()
