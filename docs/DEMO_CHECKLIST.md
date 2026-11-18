# Demo checklist (Project Expo, 20 Nov 2026)

## Demo logins (password for all: `Demo@1234`)
| Role | Email | Use in demo |
|---|---|---|
| Admin | admin@mealloop.com | Approve `helpers@mealloop.com` |
| Provider | canteen@mealloop.com | List food, accept a request |
| NGO (verified) | hope@mealloop.com | Browse and request food |
| NGO (unverified) | helpers@mealloop.com | Shows it is blocked until approved |

## Day before (19 Nov)
- [ ] Render `/health` returns {"status":"ok"} and the home page loads
- [ ] Latest `main` run is green (test, coverage, integration, deploy)
- [ ] `docker compose down -v && docker compose up -d --build` works on the demo laptop
- [ ] All 4 demo logins work on the live URL and in local Docker
- [ ] Full click-through done: request -> accept -> collect -> Impact page shows numbers
- [ ] Screen recording of the full demo saved on the laptop AND a phone/pen drive
- [ ] Screenshots of a green Actions run, the Packages page, and the live app
- [ ] Laptop charged, charger packed, phone hotspot tested
- [ ] No merges to `main` after Thursday afternoon (every merge redeploys Render)

## 15 minutes before
- [ ] Docker Desktop open, "Engine running"
- [ ] Open the Render URL once to wake it (free tier sleeps, first load ~60s)
- [ ] Browser tabs open: repo, Actions, Packages, Render dashboard, live app
- [ ] VS Code open on the project, terminal in the `mealloop` folder

## Live demo script (about 8 minutes)
1. **Show the app** (live URL): provider lists food, NGO requests it, provider
   accepts, NGO marks collected, Impact page updates. (2 min)
2. **Show verification**: log in as `helpers@mealloop.com` (blocked), approve as
   admin, log in again (allowed). (1 min)
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

## Tip for adding food live
Set the expiry at least 8 hours ahead. The server runs in UTC and you type IST.

## One-liners for the examiner
- "Every pull request is automatically linted, tested and container-checked."
- "Nothing reaches main without a green pipeline and a teammate's approval."
- "A merge to main deploys automatically; the image is tagged with the commit SHA."
- "Image = recipe, container = running instance."

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