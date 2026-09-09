# FiboTask — To-Do List + Fibonacci Generator (Django)

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
Open http://127.0.0.1:8000/ and http://127.0.0.1:8000/fibonacci/.

## Config (env vars)
| Var | Default | Meaning |
|-----|---------|---------|
| `SECRET_KEY` | dev fallback (do NOT use in prod) | Django secret |
| `DEBUG` | `True` | Never `True` in production |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated |
| `DATABASE_URL` | `sqlite:///db.sqlite3` | e.g. `postgres://postgres:1010@localhost:5432/todo_db` |
| `FIBONACCI_MAX_TERMS` | `1000` | DoS cap for `?n=` |

## Notes for reviewers
- Mutating actions (add / complete / delete) are POST-only with CSRF.
- Fibonacci input is validated server-side and capped (`FIBONACCI_MAX_TERMS`).
- SQLite locally, Postgres in prod via `DATABASE_URL` (12-factor).
- Run checks: `python manage.py test` and `python manage.py check --deploy`.
```
