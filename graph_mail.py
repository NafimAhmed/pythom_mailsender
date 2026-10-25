"""Send messages using Microsoft Graph with Entra application credentials.

Requires Exchange Online, Microsoft Graph application Mail.Send permission,
admin consent, and mailbox-scoped Exchange application authorization.
No user passwords or access tokens are logged.
"""

import os
import re
from urllib.parse import quote

import requests


class GraphMailError(RuntimeError):
    """A Microsoft Graph or Entra service rejected a request."""

    def __init__(self, stage, status_code):
        self.status_code = status_code
        super().__init__(f"Microsoft {stage} returned HTTP {status_code}")


def _recipients(addresses):
    return [{"emailAddress": {"address": address}} for address in addresses]


def send_via_graph(data):
    """Send a validated mail payload; returns after Graph accepts (HTTP 202)."""
    tenant = os.getenv("MS_TENANT_ID", "").strip()
    client = os.getenv("MS_CLIENT_ID", "").strip()
    secret = os.getenv("MS_CLIENT_SECRET", "")
    sender = os.getenv("MS_SENDER_EMAIL", "").strip()

    # Tenant ID is a GUID; client ID is the App registration's GUID.
    guid = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
    email = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$")
    if not guid.fullmatch(tenant) or not guid.fullmatch(client) or not secret or not email.fullmatch(sender):
        raise ValueError("MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET and MS_SENDER_EMAIL must be configured")

    # Application-only flow; this does not use the mailbox user's login password.
    token_response = requests.post(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data={
            "client_id": client,
            "client_secret": secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
        timeout=(10, 20),
    )
    if token_response.status_code != 200:
        raise GraphMailError("Entra token endpoint", token_response.status_code)

    token = token_response.json().get("access_token")
    if not token:
        raise GraphMailError("Entra token endpoint (missing access token)", 200)

    html = data.get("html")
    message = {
        "subject": data["subject"],
        "body": {
            "contentType": "HTML" if html else "Text",
            "content": html if html else data["body"],
        },
        "toRecipients": _recipients(data["to"]),
        "ccRecipients": _recipients(data["cc"]),
        "bccRecipients": _recipients(data["bcc"]),
    }
    # No sender provided by the request body: server-owned mailbox only.
    response = requests.post(
        f"https://graph.microsoft.com/v1.0/users/{quote(sender, safe='')}/sendMail",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"message": message, "saveToSentItems": True},
        timeout=(10, 30),
    )
    if response.status_code != 202:
        raise GraphMailError("Graph sendMail endpoint", response.status_code)
