# MealLoop 🍽️

[![CI](https://github.com/Vijaynaik22-7/mealloop/actions/workflows/ci.yml/badge.svg)](https://github.com/Vijaynaik22-7/mealloop/actions/workflows/ci.yml)

**Live app:** https://mealloop-latest.onrender.com
# MealLoop 🍽️

A smart food rescue platform. Food providers (canteens, hostels, restaurants, events)
list surplus food, and verified NGOs request and collect it, so edible food feeds people
instead of going to waste.

## Tech stack
Python 3.11 · Flask · Flask-SQLAlchemy · SQLite · Flask-Login · Bootstrap 5 ·
pytest · flake8 · Docker · GitHub Actions

## Team and modules
| Member | Module |
|--------|--------|
| 1 | Food Provider (`app/providers`) |
| 2 | NGO/Recipient + Admin verification (`app/recipients`, `app/admin`) |
| 3 | Priority Score + Analytics (`app/matching`, `app/analytics`) |
| 4 | DevOps: Git, Docker, CI/CD, deployment |
| 5 | Auth + UI + Integration (`app/auth`, `app/templates`) |

## Run locally

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py                   # open http://localhost:5000/health
```

## Run tests and lint

```bash
flake8
pytest
```

## Git workflow
See the "Branching convention" in this README's `CONTRIBUTING` section (below, to be added).
(Short version: branch `feature/<module>`, small PRs, pull `main` daily.)
## Contributing

## How CI/CD works in MealLoop

**CI (Continuous Integration)** checks every change automatically, before it reaches `main`.
**CD (Continuous Deployment)** ships `main` to the live site automatically.

```text
Developer pushes a branch ──> opens Pull Request into main
                                   │
                    GitHub Actions runs 3 jobs in parallel:
                    ├─ test         flake8 lint + pytest
                    ├─ coverage     pytest --cov, report saved as an artifact
                    └─ integration  build Docker image, start container,
                                    wait for healthcheck, curl /health (must be 200)
                                   │
              All green + 1 teammate approval ──> Merge allowed
                                   │
                          Merge = push to main
                                   │
                    deploy job (only on main, only if all 3 passed):
                    1. Log in to ghcr.io with GITHUB_TOKEN
                    2. Build image, push tags :<commit-sha> and :latest
                    3. Call the Render deploy hook ──> live site updates
```

| Piece | Tool | Purpose |
|---|---|---|
| Version control | Git + GitHub | Branches, pull requests, review |
| Branch protection | GitHub settings | No direct pushes; needs approval + green checks |
| Quality gate | flake8, pytest, pytest-cov | Style and correctness |
| Packaging | Docker | Same image runs on every laptop and on the server |
| Registry | ghcr.io | Stores versioned images |
| Hosting | Render (free) | Runs the container at a public URL |

**Why it matters:** broken code cannot reach `main`, and every merge goes live in minutes with no manual steps.

**Branches**
- `main` is always working and demo-ready. Nobody pushes to it directly.
- Each member works on `feature/<module>`, e.g. `feature/providers`, `feature/auth`.
- For extra tasks, use `feature/<module>-<short-task>`, e.g. `feature/providers-expiry-field`.

**Daily routine**
```bash
git checkout main
git pull origin main                  # get everyone's latest work
git checkout feature/<module>
git merge main                        # bring main into your branch
# ...work, then:
git add .
git commit -m "providers: add donation form"
git push origin feature/<module>
```
Then open a Pull Request into `main` on GitHub.

**Rules**
1. Small PRs (one feature or fix each). Open one at least once a day.
2. Pull `main` into your branch every morning to avoid big merge conflicts.
3. Every PR needs 1 approval from a teammate and a green CI check.
4. Commit messages: `<module>: <what you did>`.
5. Only edit files in your own module folder. If you must touch a shared file
   (`models.py`, `app/__init__.py`), tell the team first