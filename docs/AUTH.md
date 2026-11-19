# MealLoop: Authentication (M5)

This page explains how sign-up, login, roles and the optional email OTP work.

## 1. Setup

Run these in the `mealloop` folder (the one containing `run.py`).

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python seed.py
python run.py
```

Open http://127.0.0.1:5000

To create or reset an admin account:

```powershell
python create_admin.py --email admin@mealloop.com --password YourPassword
```

If the database changed (for example the `email_verified` column), delete
`instance/mealloop.db` (or run `docker compose down -v`) and run `seed.py` again.

## 2. Demo accounts

All of them use the demo password from `seed.py`.

| Email | Role | Notes |
|---|---|---|
| admin@mealloop.com | Admin | Approves NGOs |
| canteen@mealloop.com | Provider | Adds food |
| hope@mealloop.com | NGO (recipient) | Verified, can request food |
| helpers@mealloop.com | NGO (recipient) | NOT verified, cannot request |

## 3. Roles

| Role | How you get it | Can do |
|---|---|---|
| Provider | Self-register (auto verified) | Add food, accept or reject requests |
| Recipient (NGO) | Self-register, then wait for admin approval | Browse food, request it, mark collected (only after approval) |
| Admin | Created with `create_admin.py` only | Approve or reject NGOs, see platform stats |

Protection in code (`app/auth/utils.py`):
- `role_required("provider")` allows only that role. Others get 403.
- `verified_required` blocks an NGO that the admin has not approved yet.
- Passwords are stored hashed with Werkzeug. Plain passwords are never saved.
- Wrong email and wrong password show the same message, so nobody can guess which emails exist.

## 4. Email OTP (optional)

OTP is **OFF by default**. Nothing changes unless you switch it on.

| Setting | Meaning |
|---|---|
| `OTP_ENABLED=true` | Turns OTP on. Any other value or unset means off |
| `BREVO_API_KEY` | Brevo key for sending real emails (never put it in code) |
| `OTP_FROM_EMAIL` | Verified sender address in Brevo |
| `OTP_FROM_NAME` | Sender name (default `MealLoop`) |

Rules: 6-digit code, only its hash is stored, valid 10 minutes, 5 wrong tries
then it is locked, a new code can be sent after 60 seconds.

**Fallback:** if the key or sender is missing, or the internet is down, the
code is printed in the server terminal instead, so the flow still works.

Demo mode on a laptop (PowerShell):

```powershell
$env:OTP_ENABLED = "true"
python run.py
```

Register a new user, then read the 6-digit code in the terminal and enter it
on the verify page. Seeded demo accounts and admins are already
`email_verified`, so they can always log in.

To switch it off again: `Remove-Item Env:OTP_ENABLED` and restart.

## 5. Routes

| URL | What |
|---|---|
| `/auth/register` | Create an account |
| `/auth/login`, `/auth/logout` | Sign in and out |
| `/auth/verify` | Enter the OTP code (only when OTP is on) |
| `/auth/resend` | Send a new code (POST) |

## 6. Tests

```powershell
pytest tests/test_auth.py tests/test_otp.py tests/test_smoke_flow.py
```

The OTP tests mock the Brevo call, so no network or key is needed.

## 7. Screenshots (to add)

- [ ] Login page: `docs/img/login.png`
- [ ] Register page: `docs/img/register.png`
- [ ] Verify (OTP) page: `docs/img/verify.png`
- [ ] Unverified NGO warning: `docs/img/ngo-waiting.png`
