# Microsoft 365 Mail Sender API — Microsoft Graph Branch

**This branch is Microsoft-only.** It uses **Microsoft Graph with OAuth2 client credentials**, not Gmail SMTP. The Gmail-only implementation lives on `master`.

## Requirements

- Microsoft 365 Exchange Online sender mailbox
- Microsoft Entra ID App Registration (single tenant)
- Microsoft Graph **Mail.Send application permission**, admin consent
- Mailbox-scoped authorization via Exchange Online **RBAC for Applications** (configured by your IT/Exchange administrator)
- Python 3.9+ and dependencies in `requirements.txt`

> Mail.Send application permission is powerful. Ask the Exchange administrator to scope the application to **only the intended mailbox**. No user passwords, Microsoft OAuth tokens, or SMTP credentials should be committed.

## Windows setup

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Generate a random API key locally (never paste it into chat or GitHub):

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set your private `.env` next to `app.py`:

```env
MAIL_API_KEY=YOUR_RANDOM_PRIVATE_API_KEY
MS_TENANT_ID=YOUR_TENANT_GUID
MS_CLIENT_ID=YOUR_APP_CLIENT_GUID
MS_CLIENT_SECRET=YOUR_APP_SECRET_VALUE
MS_SENDER_EMAIL=authorized@company.com
PORT=5001
```

The `MS_CLIENT_SECRET` must be the secret **Value** (not the secret ID) from the Entra app. Never post these credentials publicly. `.env` is gitignored.

## Run

Local machine:

```powershell
.\.venv\Scripts\python.exe app.py
```

Trusted LAN only, after restricted firewall configuration:

```powershell
.\.venv\Scripts\waitress-serve.exe --host=172.17.107.171 --port=5001 app:app
```

Use HTTPS behind an authenticated reverse proxy or VPN for real multi-computer deployments. Never expose a private API key over the internet in plaintext HTTP.

## REST API

`GET /health`: server health.
`POST /api/v1/mail/send`: send a message through Microsoft Graph.

Headers:

```http
Content-Type: application/json
X-API-Key: YOUR_PRIVATE_API_KEY
```

JSON body:

```json
{
  "to": ["recipient@example.com"],
  "cc": [],
  "bcc": [],
  "subject": "Microsoft 365 Mail Test",
  "body": "Hello from Microsoft Graph",
  "html": "<h2>Hello</h2><p>Sent via Microsoft Graph.</p>"
}
```

The sender **cannot** be specified in caller JSON. It is fixed by the server's `MS_SENDER_EMAIL` and Exchange-side permissions.

Success response from Flask:

```json
{"success": true, "message": "Email accepted by Microsoft Graph", "recipient_count": 1}
```

Graph's HTTP 202 means accepted for processing, not verified inbox delivery.

## Run unit tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests mock network requests: real email is not sent. Live operation requires your company's Microsoft 365 IT authorization.

## Microsoft documentation

- https://learn.microsoft.com/en-us/graph/auth-v2-service
- https://learn.microsoft.com/en-us/graph/api/user-sendmail
- https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac

**Gmail version:** https://github.com/NafimAhmed/pythom_mailsender/tree/master
