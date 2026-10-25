"""Microsoft Graph outbound requests are mocked: no messages are sent."""
import os
import unittest
from unittest.mock import Mock, patch

from graph_mail import GraphMailError, send_via_graph


class GraphMailTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "MS_TENANT_ID": "11111111-1111-4111-8111-111111111111",
            "MS_CLIENT_ID": "22222222-2222-4222-8222-222222222222",
            "MS_CLIENT_SECRET": "dummy-secret",
            "MS_SENDER_EMAIL": "sender@example.com",
        })
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    def _data(self):
        return {
            "to": ["to@example.com"],
            "cc": ["cc@example.com"],
            "bcc": ["secret@example.com"],
            "subject": "Example",
            "body": "Plain text",
            "html": "<p>HTML</p>",
        }

    @patch("graph_mail.requests.post")
    def test_mail_send_uses_app_credentials_and_sender_mailbox(self, post):
        token_response = Mock(status_code=200)
        token_response.json.return_value = {"access_token": "test-token"}
        send_response = Mock(status_code=202)
        post.side_effect = [token_response, send_response]
        send_via_graph(self._data())

        self.assertEqual(post.call_count, 2)
        auth_url = post.call_args_list[0].args[0]
        token_kwargs = post.call_args_list[0].kwargs
        self.assertIn("/oauth2/v2.0/token", auth_url)
        self.assertEqual(token_kwargs["data"]["grant_type"], "client_credentials")
        self.assertEqual(token_kwargs["data"]["scope"], "https://graph.microsoft.com/.default")

        send_url = post.call_args_list[1].args[0]
        send_kwargs = post.call_args_list[1].kwargs
        self.assertTrue(send_url.endswith("/users/sender%40example.com/sendMail"))
        self.assertEqual(send_kwargs["headers"]["Authorization"], "Bearer test-token")
        message = send_kwargs["json"]["message"]
        self.assertEqual(message["body"], {"contentType": "HTML", "content": "<p>HTML</p>"})
        self.assertEqual(message["bccRecipients"][0]["emailAddress"]["address"], "secret@example.com")
        self.assertNotIn("from", message)
        self.assertTrue(send_kwargs["json"]["saveToSentItems"])

    @patch("graph_mail.requests.post")
    def test_graph_403_is_returned_as_upstream_error(self, post):
        token_response = Mock(status_code=200)
        token_response.json.return_value = {"access_token": "test-token"}
        post.side_effect = [token_response, Mock(status_code=403)]
        with self.assertRaises(GraphMailError) as caught:
            send_via_graph(self._data())
        self.assertEqual(caught.exception.status_code, 403)

    @patch("graph_mail.requests.post")
    def test_token_rejection_is_reported(self, post):
        post.return_value = Mock(status_code=401)
        with self.assertRaises(GraphMailError) as caught:
            send_via_graph(self._data())
        self.assertEqual(caught.exception.status_code, 401)
        post.assert_called_once()

    @patch("graph_mail.requests.post")
    def test_missing_credentials_fail_before_network_call(self, post):
        with patch.dict(os.environ, {"MS_CLIENT_SECRET": ""}):
            with self.assertRaises(ValueError):
                send_via_graph(self._data())
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
