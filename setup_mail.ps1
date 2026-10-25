# Creates a LOCAL .env file. Never commit or share it.
# Run from PowerShell: powershell -NoProfile -File .\setup_mail.ps1
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$envPath = Join-Path $PSScriptRoot ".env"

Write-Host "Flask Mail Sender - Secure Local Configuration"
Write-Host "The Gmail App Password displayed in a screenshot must be revoked before proceeding."
Write-Host ""

if (Test-Path -LiteralPath $envPath) {
    $confirmation = Read-Host "A .env already exists. Type YES to replace it (old settings will be lost)"
    if ($confirmation -cne "YES") {
        Write-Host "Cancelled. Existing .env was not changed."
        exit 0
    }
}

$email = (Read-Host "Gmail sender address").Trim()
if ($email -notmatch '^[A-Za-z0-9._%+-]+@gmail\.com$') {
    throw "Enter a valid @gmail.com address."
}

Write-Host "Paste your NEW 16-character Google App Password (input hidden)."
$securePassword = Read-Host "Google App Password" -AsSecureString
$password = [System.Net.NetworkCredential]::new("", $securePassword).Password
$password = $password -replace '\s+', ''

if ($password -notmatch '^[A-Za-z0-9]{16}$') {
    throw "Google App Password must contain 16 letters/digits (spaces are ignored). No file was changed."
}

$randomBytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $rng.GetBytes($randomBytes)
}
finally {
    $rng.Dispose()
}
$apiKey = [Convert]::ToBase64String($randomBytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')

# Use an absolute path so PyCharm and a terminal can read the same .env.
# All interpolated values are validated to avoid injecting additional .env keys.
$configuration = @"
MAIL_API_KEY=$apiKey
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=$email
SMTP_PASSWORD=$password
SMTP_FROM=$email
PORT=5000
"@

[System.IO.File]::WriteAllText(
    $envPath,
    $configuration + [Environment]::NewLine,
    (New-Object System.Text.UTF8Encoding($false))
)
Remove-Variable -Name password, securePassword -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Configuration saved locally: $envPath"
Write-Host "A new random MAIL_API_KEY has been generated (length: $($apiKey.Length))."
Write-Host "The API Key and App Password were NOT uploaded to GitHub."
Write-Host "Stop/restart your Flask server to load these values."
Write-Host "Set Postman collection variable 'api_key' to MAIL_API_KEY from your LOCAL .env file."
