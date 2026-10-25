# Flask Mail Sender API

Authenticated JSON REST endpoint that sends plain text / HTML email over any username-password SMTP server (including Gmail). Supports To, Cc, Bcc. SMTP acceptance does not guarantee inbox delivery.

## Quick start (Windows / macOS / Linux)

Install **Python 3.9+**.

```bash
python -m venv .venv
```

Activate it:
- **Windows PowerShell**: `.venv\Scripts\Activate.ps1`
- **Windows CMD**: `.venv\Scripts\activate.bat`
- **macOS / Linux**: `source .venv/bin/activate`

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and provide real SMTP credentials. Never commit `.env` to Git. Generate a strong key with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

For **Gmail**:
1. Turn on 2-Step Verification.
2. Generate an App Password if your account allows it: https://myaccount.google.com/apppasswords
3. Set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_SECURITY=starttls` and use your Gmail address for `SMTP_USER` / `SMTP_FROM`. Set `SMTP_PASSWORD` to the **App Password**, not your normal login password. Google may restrict availability of App Passwords for some accounts.

Start local dev server:

```bash
python app.py
```

For deployment, put behind **HTTPS + authentication / IP allowlist**, add persistent rate limiting (e.g. Redis-backed) at gateway, and use a production WSGI server:

```bash
waitress-serve --host 0.0.0.0 --port 5000 app:app
```

If exposed beyond a trusted network, do **not** put `MAIL_API_KEY` in a shipped Flutter/mobile app; it can be extracted. Route through a backend that authenticates users and enforces authorization + rate limits.

## API

`GET /health` — health check.

`POST /api/v1/mail/send` — request headers:

```
Content-Type: application/json
X-API-Key: your-generated-secret
```

JSON body (a string or array can be used for each recipient field):

```json
{
  "to": ["recipient@example.com"],
  "cc": ["manager@example.com"],
  "bcc": "audit@example.com",
  "subject": "Hello from Flask",
  "body": "This is a test email.",
  "html": "<h2>Hello from Flask</h2><p>This is a test email.</p>"
}
```

Required fields: `to`, `subject`, at least one of `body` or `html`. Up to 20 distinct recipient addresses. Body limits: 100k characters each. Request cap: 256 KB.

Successful SMTP acceptance (HTTP 200):

```json
{"success": true, "message": "Email accepted by SMTP server", "recipient_count": 3}
```

Other statuses: `400` invalid JSON or fields, `401` invalid/missing API key, `413` oversized body, `415` wrong Content-Type, `502` upstream SMTP failure (or partial rejection), `503` missing/bad server configuration.

### cURL / Postman

```bash
curl -X POST http://127.0.0.1:5000/api/v1/mail/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: REPLACE_WITH_YOUR_KEY" \
  -d '{"to":"recipient@example.com","subject":"Test Mail","body":"Hello from Flask!"}'
```

Use Postman with `POST`, URL `http://127.0.0.1:5000/api/v1/mail/send`, raw JSON body, and both required headers above.

## Run tests

```bash
python -m unittest discover -s tests -v
```

No real SMTP messages are sent in the tests.

## Notes

- SMTP authentication uses TLS (`STARTTLS` port 587 or implicit SSL port 465). This example deliberately does not implement unauthenticated SMTP or OAuth2.
- Sender address must normally be an address authorized by the SMTP provider; otherwise the provider may rewrite or reject the email.
- Never log or commit secrets, and never expose this API directly to arbitrary clients without additional protections.
