"""Authenticated Flask API for sending email through Microsoft Graph (OAuth2)."""

import hmac
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from graph_mail import GraphMailError, send_via_graph

import requests

# Read the .env beside this file, regardless of the PyCharm working directory.
# A local .env takes priority over old MAIL_API_KEY values in the shell.
BASE_DIR = Path(__file__).resolve().parent


def load_project_env():
    env_file = BASE_DIR / ".env"
    if env_file.is_file():
        load_dotenv(dotenv_path=env_file, override=True)


load_project_env()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024  # 256 KiB JSON request limit
logging.basicConfig(level=logging.INFO)

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$")
MAX_RECIPIENTS = 20
MAX_BODY_LENGTH = 100_000


class BadRequest(ValueError):
    """Raised for invalid caller input."""


def parse_emails(value, field, required=False):
    """Accept one email string or a list of emails; reject malformed addresses."""
    if value is None and not required:
        return []
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        items = value
    else:
        raise BadRequest(f"'{field}' must be an email string or list of email strings")

    if required and not items:
        raise BadRequest(f"'{field}' is required")

    cleaned = []
    for item in items:
        email = item.strip()
        if len(email) > 254 or not EMAIL_RE.fullmatch(email) or ".." in email:
            raise BadRequest(f"Invalid email address in '{field}'")
        cleaned.append(email)
    return cleaned


def validate_payload(payload):
    if not isinstance(payload, dict):
        raise BadRequest("JSON object required")

    to = parse_emails(payload.get("to"), "to", required=True)
    cc = parse_emails(payload.get("cc"), "cc")
    bcc = parse_emails(payload.get("bcc"), "bcc")
    recipients = list(dict.fromkeys([*to, *cc, *bcc]))
    if len(recipients) > MAX_RECIPIENTS:
        raise BadRequest(f"Maximum {MAX_RECIPIENTS} distinct recipients allowed")

    subject = payload.get("subject")
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 255:
        raise BadRequest("'subject' is required and must be 1-255 characters")
    if "\r" in subject or "\n" in subject:
        raise BadRequest("'subject' must not contain newlines")

    body = payload.get("body")
    html = payload.get("html")
    if body is not None and (not isinstance(body, str) or len(body) > MAX_BODY_LENGTH):
        raise BadRequest("'body' must be text of at most 100000 characters")
    if html is not None and (not isinstance(html, str) or len(html) > MAX_BODY_LENGTH):
        raise BadRequest("'html' must be text of at most 100000 characters")
    if not body and not html:
        raise BadRequest("Provide non-empty 'body' or 'html'")

    return {"to": to, "cc": cc, "bcc": bcc, "recipients": recipients,
            "subject": subject.strip(), "body": body, "html": html}


@app.get("/health")
def health():
    return jsonify({"success": True, "service": "flask-mail-sender"}), 200


@app.post("/api/v1/mail/send")
def send_mail():
    expected_key = os.getenv("MAIL_API_KEY", "").strip()
    if not expected_key:
        return jsonify({"success": False, "error": "MAIL_API_KEY is not configured"}), 503

    supplied_key = request.headers.get("X-API-Key", "").strip()
    if not hmac.compare_digest(supplied_key, expected_key):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    if not request.is_json:
        return jsonify({"success": False, "error": "Content-Type must be application/json"}), 415

    try:
        payload = validate_payload(request.get_json(silent=True))
    except BadRequest as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    try:
        send_via_graph(payload)
    except ValueError:
        app.logger.error("Microsoft Graph configuration is incomplete")
        return jsonify({"success": False, "error": "Microsoft Graph is not configured correctly"}), 503
    except GraphMailError as exc:
        app.logger.error("%s", exc)
        return jsonify({"success": False, "error": "Microsoft Graph authorization or delivery error",
                        "upstream_status": exc.status_code}), 502
    except requests.exceptions.RequestException:
        app.logger.exception("Microsoft Graph connection failed")
        return jsonify({"success": False, "error": "Microsoft Graph connection error"}), 502

    # Microsoft Graph returns HTTP 202 for accepted processing, not inbox delivery.
    return jsonify({"success": True, "message": "Email accepted by Microsoft Graph",
                    "recipient_count": len(payload["recipients"])}), 200


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"success": False, "error": "Request body too large"}), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
