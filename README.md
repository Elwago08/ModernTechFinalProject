# Video Game Rating Software

A Flask application for keeping a game library and recording personal ratings.

## Current features

- Add games to the library.
- Optionally rate a game when adding it, or add/edit its rating later.
- Score Gameplay, Story, Graphics, Music, and Difficulty from 1 to 10.
- Calculate an overall score as the average of the five category scores.
- Add optional notes to each category and an overall note.
- Search the library by a case-insensitive part of a game title.

## Upcoming features

- User registration, login, and authentication.
- Separate libraries and ratings for each user.
- Further improvements to the game details and rating experience.

## Using the application

The current app uses a shared `demo` user; authentication has not been
implemented. Anyone who can access the running app can see and change that
library.

1. Open the application's home page to see the library.
2. Select **Add a game** and enter a title. Category scores are optional, but
   either leave all five blank or provide a score from 1 to 10 for each.
   Category notes and the overall note are also optional and can be entered
   even when no scores are provided.
3. Use **Search** to find games by title. The search matches part of a title
   and ignores letter case. Use **Clear** to show the full library again.
4. Select **Rate game** for an unrated game to add scores or notes. Select
   **View rating** for a game with saved rating data to see its overall score,
   category scores, and notes. Choose **Edit rating** from that page to make
   changes.
5. Select **Remove** to remove a game from the demo user's library. This also
   removes its rating and notes, but leaves the game record in the database.

## Setup

Requires Python 3.10 or later.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m flask --app run.py init-db
python run.py
```

Open <http://127.0.0.1:5000>. The SQLite database is stored at
`instance/project.db`. `init-db` can be run again; it creates missing tables
and the demo user without erasing existing data. The default secret key is for
local development only. Set the `SECRET_KEY` environment variable when
deploying. To run the tests:

```powershell
python -m unittest discover -s tests
```

## Tech stack

- Frontend: HTML and CSS rendered with Flask
- Backend: Python and Flask
- Database: SQLite locally or PostgreSQL on Cloud Run, accessed through
  SQLAlchemy

## AI Usage
This project was coded almost exclusively using generative AI tools, such as Copilot. All major design descisions and supervision of the entire project was done by me.