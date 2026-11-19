@'
# MealLoop: Authentication (M5)

How sign-up, login, roles and the optional email OTP work.

## 1. Setup

Run in the `mealloop` folder (the one containing `run.py`):

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python seed.py
python run.py
```

Open http://127.0.0.1:5000

Create or reset an admin:

```powershell
python create_admin.py --email admin@mealloop.com --password YourPassword
```

If the database model changed (for example the `email_verified` column),
delete `instance/mealloop.db` (or run `docker compose down -v`) and start again.

## 2. Demo accounts

All use the demo password from `seed.py`.

| Email | Role | Notes |
|---|---|---|
| admin@mealloop.com | Admin | Approves NGOs |
| canteen@mealloop.com | Provider | Adds food |
| hope@mealloop.com | NGO | Verified, can request food |
| helpers@mealloop.com | NGO | NOT verified, cannot request |

## 3. Roles

| Role | How you get it | Can do |
|---|---|---|
| Provider | Self-register (auto verified) | Add food, accept or reject requests |
| Recipient (NGO) | Self-register, then admin approval | Browse and request food, mark collected |
| Admin | `create_admin.py` only | Approve or reject NGOs, see stats |

Protection in code (`app/auth/utils.py`):

- `role_required("provider")` allows only that role; others get 403.
- `verified_required` blocks an NGO the admin has not approved.
- Passwords are hashed with Werkzeug; plain passwords are never stored.
- Wrong email and wrong password show the same message.
- The `next` redirect only accepts addresses inside the site.

## 4. Email OTP (optional)

OTP is OFF by default.

| Setting | Meaning |
|---|---|
| `OTP_ENABLED=true` | Turns OTP on (anything else means off) |
| `BREVO_API_KEY` | Brevo key for real emails (never put it in code) |
| `OTP_FROM_EMAIL` | Sender address verified in Brevo |
| `OTP_FROM_NAME` | Sender name (default `MealLoop`) |

Rules: 6-digit code, only its hash is stored, valid 10 minutes, locked after
5 wrong tries, a new code only after 60 seconds.

Fallback: if the key or sender is missing, or the internet is down, the code
is printed in the server terminal, so the flow still works.

Demo mode on a laptop (PowerShell):

```powershell
$env:OTP_ENABLED = "true"
python run.py
```

Register a new user, read the code in the terminal, enter it on the verify
page. Seeded demo accounts and admins are already `email_verified`.

Switch off again: `Remove-Item Env:OTP_ENABLED`, then restart.

## 5. Routes

| URL | What |
|---|---|
| /auth/register | Create an account |
| /auth/login, /auth/logout | Sign in and out |
| /auth/verify | Enter the OTP code (only when OTP is on) |
| /auth/resend | Send a new code (POST) |

## 6. Tests

```powershell
pytest tests/test_auth.py tests/test_otp.py tests/test_smoke_flow.py
```

The OTP tests mock the Brevo call, so no key or internet is needed.

## 7. Known limitation

There are no CSRF tokens on forms yet. A future improvement is Flask-WTF
CSRFProtect.

## 8. Screenshots (to add)

- [ ] Login page: docs/img/login.png
- [ ] Register page: docs/img/register.png
- [ ] Verify (OTP) page: docs/img/verify.png
- [ ] Unverified NGO warning: docs/img/ngo-waiting.png
'@ | Set-Content -Path docs\AUTH.md -Encoding ascii
