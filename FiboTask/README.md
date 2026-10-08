# FiboTask - size it, split it, start it (Django)

Student productivity app: estimate tasks in Fibonacci points, split 8+ into steps (Rule of 8), beat procrastination with Fibonacci focus timers (1→2→3→5→13 ladder). Pages: Tasks, Focus, Lab + animated landing and 3-minute guide. No frontend dependencies, no accounts — local-first.

## MVP scope (what "complete" means here)
- [x] Tasks with course, priority, points (1–21), due dates, notes, search/filter/sort
- [x] Rule of 8: subtasks on every task, split nudge on 8+
- [x] Sprint planning: capacity, auto-plan, velocity
- [x] Focus room: Fibonacci timer, escalation ladder, session log, today + week stats
- [x] First-run: sample tasks seeder, empty-state guide
- [x] Portability: CSV export · Docs: landing + guide · Theming: light/dark, responsive
- [ ] Out of MVP (later): accounts/sync, reminders, streaks, PWA offline

## Quickstart (Windows PowerShell)
```powershell
cd FiboTask
python -m venv ..\venv  # or reuse existing
..\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # edit SECRET_KEY / DATABASE_URL as needed
python manage.py migrate
python manage.py runserver
```
Open http://127.0.0.1:8000/ · http://127.0.0.1:8000/focus/ · http://127.0.0.1:8000/fibonacci/.

New? Start at http://127.0.0.1:8000/welcome/ (animated one-look intro) then http://127.0.0.1:8000/guide/ (3-minute docs).

## Deploy (Render, free tier)
1. Push this repo to GitHub (do not commit `.env`, `db.sqlite3`, or `staticfiles/`).
2. Go to dashboard.render.com → New → Blueprint → select the repo (`render.yaml` is at the root).
3. Render generates `SECRET_KEY`, sets `DEBUG=false`, and runs collectstatic + migrate on every deploy.
4. Open `https://<your-name>.onrender.com/welcome/`. First boot is slow on the free tier (it sleeps when idle).

Know before you share the link:
- The free service uses **ephemeral SQLite**: all visitors share one list, and restarts wipe it. Fine for a demo, not for real use. Postgres + accounts is the next milestone.
- If Render rejects `PYTHON_VERSION: 3.13.4`, replace it with a version from the error message (any 3.12+ works with Django 6).
- Custom domain? Append it to `ALLOWED_HOSTS` in the Render dashboard (comma-separated).

## Config (env vars)
| Var | Default | Meaning |
|-----|---------|---------|
| `SECRET_KEY` | dev fallback (do NOT use in prod) | Django secret |
| `DEBUG` | `True` | Never `True` in production |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated |
| `DATABASE_URL` | `sqlite:///db.sqlite3` | e.g. `postgres://postgres:1010@localhost:5432/todo_db` |
| `FIBONACCI_MAX_TERMS` | `1000` | DoS cap for `?n=` |

## Notes for reviewers
- Mutating actions (tasks, subtasks, sprint, snooze, focus-log, lab-create, seed) are POST-only with CSRF.
- Tasks: `?q=` (title/notes/course), `?status=all|today|sprint|active|done|overdue`, `?course=`, `?sort=newest|oldest|priority|points|due|title`, 8/page, `/` focuses search.
- Estimates locked to 1,2,3,5,8,13,21 with student guide; 8+ shows “split it” until subtasks exist; sprint capacity in session (default 21, `?capacity=`); snooze steps +1/+2/+3/+5/+8/+13d.
- Focus: `/focus/?minutes=13&task=<id>` presets 1–34, JS countdown, POST `focus/log/` (1–90 min, honest partial logging), suggested breaks 1/3/5/8; ladder 1→2→3→5→13; today + week stats.
- First-run: POST `samples/` seeds 3 guided tasks (empty list only). Portability: GET `export/` downloads tasks CSV.
- Lab estimator (`?points=`) POSTs to `fibonacci/create-task/`; sequence capped by `FIBONACCI_MAX_TERMS`.
- SQLite locally, Postgres in prod via `DATABASE_URL` (12-factor).
- Run checks: `python manage.py test` (32 tests) and `python manage.py check --deploy`.
```
