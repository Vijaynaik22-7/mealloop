# Demo checklist (Project Expo, 20 Nov 2026)

## Demo logins (password for all: `Demo@1234`)
| Role | Email | Use in demo |
|---|---|---|
| Admin | admin@mealloop.com | Approve `helpers@mealloop.com` |
| Provider | canteen@mealloop.com | List food, accept a request |
| NGO (verified) | hope@mealloop.com | Browse and request food |
| NGO (unverified) | helpers@mealloop.com | Shows it is blocked until approved |

## Thursday (19 Nov)
- [ ] LAST merge to `main` by midday, then feature freeze (bug fixes only, each with a PR and a review)
- [ ] After the last merge: Render deploy finished and the logs show the "Seeded" line
- [ ] Render `/health` returns {"status":"ok"} and the home page loads
- [ ] Latest `main` run is green (test, coverage, integration, deploy)
- [ ] All 4 demo logins work on the live URL (log in only; do NOT run the request flow on the live site)
- [ ] `docker compose down -v && docker compose up -d --build` works on the demo laptop
- [ ] Full click-through on LOCAL Docker (see script step 1), then Impact page shows numbers
- [ ] Screen recording of the full demo saved on the laptop AND a phone/pen drive
- [ ] Screenshots of a green Actions run, the Packages page, and the live app
- [ ] Two rehearsals done (the 2nd with a teammate acting as the examiner)
- [ ] Offline fallback practised once (hotspot off, local Docker only)
- [ ] Laptop charged, charger packed, phone hotspot tested

## Friday (20 Nov), before the expo
- [ ] Merge NOTHING (every merge redeploys Render and re-seeds the data)
- [ ] 15 min early: open the Render URL once to wake it (first load about 60s)
- [ ] Actions page: latest `main` run is green
- [ ] Docker Desktop open, "Engine running"
- [ ] Browser tabs open: repo, Actions, Packages, Render dashboard, live app
- [ ] VS Code open on the project, terminal in the `mealloop` folder

## Live demo script (about 8 minutes)
1. **Show the app** (live URL). (2 min)
   1. Log in as `canteen@mealloop.com` and add a food item
      (expiry at least 8 hours ahead).
   2. Log out, log in as `hope@mealloop.com`, open **Find Food**, request it.
   3. Open **My Requests** to show the status is "pending".
   4. Log out, log in as the provider again: **Dashboard -> View Requests -> Accept**.
   5. On the same page click **Mark as collected**.
   6. Open **Impact**: the numbers updated.
2. **Show verification**: log in as `helpers@mealloop.com` (blocked), approve as
   admin (**Verify NGOs**), log in again (allowed). (1 min)
3. **Make a small change**: edit one line (e.g. footer text) on a branch.
   `git checkout -b feature/demo-change`, commit, push, open PR. (1 min)
4. **Show CI running**: PR checks `test`, `coverage`, `integration` turn green.
   Open the `integration` log: "healthy" and "HTTP status: 200". (1 min)
5. **Show branch protection**: merge button blocked until approval. Approve
   (teammate) and merge. (1 min)
6. **Show CD**: Actions run on `main`, `deploy` job green, then the new package
   tag in Packages and the Render Events deploy. (1 min)
7. **Show Docker**: (1.5 min)
   - `docker images mealloop`  -> the IMAGE (blueprint)
   - `docker compose up -d` / `docker ps`  -> the CONTAINER (running instance, "healthy")
   - `docker logs mealloop`, `docker exec -it mealloop whoami` -> `appuser` (non-root)
   - "One image can start many containers": run a second on port 5001
8. **Show the coverage report**: download artifact, open `htmlcov/index.html`.

NOTE: Steps 3 to 6 merge to `main`, which redeploys Render and re-seeds the
data. Do the app flow (step 1) BEFORE the merge, or run step 1 on local Docker.
If the live demo is a real merge, use a tiny change (footer text) and revert
nothing afterwards; the freeze rule applies to everything else.

## Tip for adding food live
Set the expiry at least 8 hours ahead. The server runs in UTC and you type IST.

## One-liners for the examiner
- "Every pull request is automatically linted, tested and container-checked."
- "Nothing reaches main without a green pipeline and a teammate's approval."
- "A merge to main deploys automatically; the image is tagged with the commit SHA."
- "Image = recipe, container = running instance."

## Honest answers if the examiner asks about limits
- Free Render sleeps after about 15 min idle and wipes SQLite on every deploy,
  so the seed script re-creates the demo data on each start.
- SQLite is used for simplicity; production would use PostgreSQL.
- No CSRF protection yet and passwords need only 6 characters; first things to
  harden next.
- Provider expiry validation uses local time while the rest uses UTC; that is
  why we set expiry at least 8 hours ahead.
- Expired donations are cleaned by `flask analytics expire-donations`, not
  automatically; a scheduler would be the next step.
- The Impact chart shows one bar because the seed creates everything today.

## Fallback plan if venue internet fails
1. **Phone hotspot**: connect the laptop, retry (the Actions page is light).
2. **Run locally with Docker** (works offline once the image is built):
   `docker compose down -v && docker compose up -d --build`, then open
   http://localhost:5000. Show `docker images`, `docker ps`, `docker logs`.
3. **Run the checks locally** to replace the CI demo:
   `flake8` then `pytest --cov=app` then `docker build -t mealloop:ci .`
4. **Play the screen recording** of the full flow (push, green Actions run,
   deploy, live app) and say "this is the recording from yesterday".
5. **Show screenshots/PDF** of the green run, Packages page and Render dashboard.

## Recording the fallback video (Windows)
- Press **Win + G** (Xbox Game Bar) then Record, or use OBS Studio.
- Record: PR opened -> checks green -> merge -> deploy green -> live app -> docker commands.
- Keep it under 5 minutes. Save a copy on a phone.