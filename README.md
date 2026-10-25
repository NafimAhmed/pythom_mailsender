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


## Fixing `401 Unauthorized` on Windows / PyCharm

This version loads the `.env` file **next to `app.py`**, regardless of the current working directory (including PyCharm's test runner), and gives it priority over stale values in the parent shell.

1. Copy `.env.example` to `.env` **in the folder containing `app.py`** and set a strong `MAIL_API_KEY`. Do not put the literal placeholder into Postman.
2. In Postman, set the collection variable `api_key` to the exact `MAIL_API_KEY` value (without `Bearer`), or use `X-API-Key` directly in the request headers. An `Unauthorized` response means the submitted key is missing or differs from the server's configured key.
3. Stop and restart Flask after editing `.env`.
4. Verify that the file contains a configured key without printing the secret:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from dotenv import dotenv_values; p=Path('app.py').resolve().parent/'.env'; k=(dotenv_values(p).get('MAIL_API_KEY') or '').strip(); print('Found .env:',p.is_file(),'Key configured:',bool(k),'Key length:',len(k))"
```

You can test without manually pasting the key by running the following **in a second PowerShell window** from the project directory while Flask is running:

```powershell
$key = ((Get-Content .env | Where-Object { $_ -match '^MAIL_API_KEY=' } | Select-Object -First 1) -split '=', 2)[1].Trim()
$body = @{ to = @('receiver@example.com'); subject = 'Flask Test'; body = 'Hello from Flask' } | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/v1/mail/send' -Method POST -Headers @{ 'X-API-Key' = $key } -ContentType 'application/json' -Body $body
```

Change `receiver@example.com` to your own test recipient. A `502 SMTP authentication failed` response is a **separate issue** from a `401` API key mismatch; Gmail normally needs a valid 16-character Google App Password instead of the account password.

**Security:** Rotate any API key or SMTP password previously shared in screenshots or chat. The real `.env` belongs only on your machine and must never be committed. The `.env.example` file intentionally contains placeholders.

## Set credentials securely on Windows (recommended)

**Do not send App Passwords or API keys in chat, screenshots, issues, or public commits.** If one was exposed, revoke it in Google Account settings and generate a new one.

Run the local setup assistant from the repository root in PowerShell:

```powershell
powershell -NoProfile -File .\setup_mail.ps1
```

It asks for the sender Gmail address and a **new** 16-character Google App Password (entered invisibly), generates a cryptographically random API key, and writes **only your local** `.env` beside `app.py`. If `.env` already exists, you must type `YES` to overwrite it; otherwise the script changes nothing. No credential is committed or sent to GitHub.

If PowerShell blocks running local scripts, use a process-only execution-policy override for this trusted repository script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup_mail.ps1
```

Restart Flask after setup. In Postman set the `api_key` collection variable to `MAIL_API_KEY` from your local `.env` file. **The generated key is not printed to the console.** For security, never paste your private key into GitHub.


## Microsoft 365 Outlook sender (Microsoft Graph app-only OAuth2)

For an **Exchange Online** mailbox, use Microsoft Graph instead of Gmail SMTP.
**This requires IT/admin approval.** Simply being able to sign in to Outlook does not prove the mailbox supports this integration.

1. Ask your Microsoft 365 admin to register a single-tenant app in https://entra.microsoft.com/.
2. Under **API Permissions**, choose **Microsoft Graph > Application permissions > Mail.Send**, and grant admin consent. **Mail.Send application permission is powerful**: by default it may allow sending as any mailbox. Restrict permissions to the intended sender using Exchange Online **RBAC for Applications**; do not use a tenant-wide send permission without appropriate scoping.
3. Record Tenant (directory) ID, Application (client) ID, and a newly created client secret (the secret **Value**, not its ID). Keep them private.
4. In the local (never committed) .env, use:

```env
MAIL_PROVIDER=graph
MAIL_API_KEY=YOUR_PRIVATE_API_KEY
MS_TENANT_ID=YOUR_TENANT_GUID
MS_CLIENT_ID=YOUR_APPLICATION_CLIENT_GUID
MS_CLIENT_SECRET=YOUR_NEW_CLIENT_SECRET
MS_SENDER_EMAIL=mailbox@company.com
PORT=5001
```

5. Install updated dependencies: `python -m pip install -r requirements.txt`; restart the Flask or Waitress process.
6. Test the **same** POST `/api/v1/mail/send` with the same `X-API-Key` header and `to`, `cc`, `bcc`, `subject`, `body`, and `html` fields. Sender is configured server-side, not accepted from client JSON.
7. A response of HTTP 200 from Flask means Graph returned HTTP 202 **Accepted**. Microsoft Graph does not guarantee inbox delivery.

The Graph OAuth flow requests a token from `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token` with scope `https://graph.microsoft.com/.default` and calls `POST https://graph.microsoft.com/v1.0/users/{mailbox}/sendMail`.

Errors: A `503` can mean missing Graph configuration. A `502` with `upstream_status: 401` normally indicates invalid token/audience; `403` normally indicates missing consent/authorization or mailbox scope; `404` can indicate an incorrect mailbox. Ask IT to inspect application permissions and Exchange Online mailbox authorization. Never log secrets, tokens, or full privileged request headers.

You can revert to Gmail SMTP by setting `MAIL_PROVIDER=smtp` and restarting, using the original `SMTP_*` variables.

References:
- https://learn.microsoft.com/en-us/graph/auth-v2-service
- https://learn.microsoft.com/en-us/graph/api/user-sendmail
- https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac
