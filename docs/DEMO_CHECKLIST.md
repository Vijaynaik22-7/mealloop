# Demo checklist (Project Expo, 21 Nov 2026)

## Day before (20 Nov)
- [ ] Render `/health` returns {"status":"ok"} (fix the 500 on `/` first)
- [ ] Latest `main` run is green (test, coverage, integration, deploy)
- [ ] `docker compose down -v && docker compose up -d --build` works on the demo laptop
- [ ] Demo accounts and sample data are ready (admin, provider, NGO)
- [ ] Screen recording of the full demo saved on the laptop AND a phone/pen drive
- [ ] Screenshots of a green Actions run, the Packages page, and the live app
- [ ] Laptop charged, charger packed, phone hotspot tested
- [ ] Do NOT deploy for the first time on 18 Nov (Render maintenance)

## 15 minutes before
- [ ] Docker Desktop open, "Engine running"
- [ ] Open the Render URL once to wake it (free tier sleeps, first load ~60s)
- [ ] Browser tabs open: repo, Actions, Packages, Render dashboard, live app
- [ ] VS Code open on the project, terminal in the `mealloop` folder

## Live demo script (about 8 minutes)
1. **Show the app** (live URL): provider lists food, NGO requests it. (1.5 min)
2. **Make a small change**: edit one line (e.g. footer text or README) on a branch.
   `git checkout -b feature/demo-change`, commit, push, open PR. (1 min)
3. **Show CI running**: PR checks `test`, `coverage`, `integration` turn green.
   Open the `integration` log: "healthy" and "HTTP status: 200". (1.5 min)
4. **Show branch protection**: merge button blocked until approval. Approve
   (teammate) and merge. (1 min)
5. **Show CD**: Actions run on `main`, `deploy` job green, then the new package
   tag in Packages and the Render Events deploy. (1.5 min)
6. **Show Docker**: (1.5 min)
   - `docker images mealloop`  -> the IMAGE (blueprint)
   - `docker compose up -d` / `docker ps`  -> the CONTAINER (running instance, "healthy")
   - `docker logs mealloop`, `docker exec -it mealloop whoami` -> `appuser` (non-root)
   - "One image can start many containers": run a second on port 5001
7. **Show the coverage report**: download artifact, open `htmlcov/index.html`. (0.5 min)
8. **Show it can fail**: (optional) a branch where `/health` returns 500 makes
   `integration` go red and blocks the merge.

## One-liners for the examiner
- "Every pull request is automatically linted, tested and container-checked."
- "Nothing reaches main without a green pipeline and a teammate's approval."
- "A merge to main deploys automatically; the image is tagged with the commit SHA."
- "Image = recipe, container = running instance."

## Fallback plan if venue internet fails
1. **Phone hotspot**: connect the laptop, retry (the Actions page is light).
2. **Run locally with Docker** (works offline once the image is built):
   `docker compose up -d --build` then open http://localhost:5000
   Show `docker images`, `docker ps`, `docker logs`, `docker exec`.
3. **Run the checks locally** to replace the CI demo:
   `flake8` then `pytest --cov=app` then `docker build -t mealloop:ci .`
4. **Play the screen recording** of the full flow (push, green Actions run,
   deploy, live app) and say "this is the recording from yesterday".
5. **Show screenshots/PDF** of the green run, Packages page and Render dashboard.

## Recording the fallback video (Windows)
- Press **Win + G** (Xbox Game Bar) then Record, or use OBS Studio.
- Record: PR opened -> checks green -> merge -> deploy green -> live app -> docker commands.
- Keep it under 5 minutes. Save a copy on a phone.