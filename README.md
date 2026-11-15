# mealloop
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