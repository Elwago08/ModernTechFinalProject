# Video Game Rating Software

This project is a starting point for tracking a personal game library and rating
games based on individual preferences.

## Features planned
- User accounts and login
- A personal game library
- Overall and customizable criteria-based ratings
- Notes on ratings
- Searching a user's library

## Getting started

Requires Python 3.10 or later.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m flask --app run.py init-db
python run.py
```

Open <http://127.0.0.1:5000> to add or remove games from the demo user's
library. Removing a game removes its library entry and associated rating, but
keeps the game record. The SQLite database is created at `instance/project.db`.
The `init-db` command
creates a `demo` user with a generated unusable password hash for development;
authentication is not implemented yet. To run the tests:

```powershell
python -m unittest discover -s tests
```

The app factory and database extension live in `app/__init__.py`; starter data
models are in `app/models.py`. `init-db` creates the tables and can be run again
if needed. It does not erase existing data. The default secret key is for local
development only; set the `SECRET_KEY` environment variable before deploying.

## Tech Stack
- Frontend: HTML + CSS with Flask
- Backend: Python
- Database: SQLite with SQLAlchemy
