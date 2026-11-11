# Video Game Rating Software

This project is a starting point for tracking a personal game library and rating
games based on individual preferences.

## Features planned
- User accounts and login
- A personal game library
- Game ratings for Gameplay, Story, Graphics, Music, and Difficulty
- An overall rating calculated as the average of those five scores
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

Open <http://127.0.0.1:5000> to view the demo user's library. Choose **Add a
game** to open the game form. You can optionally rate the game there by scoring
all five categories from 1 to 10, or leave all category scores blank and rate it
later using **Rate game** beside the library entry. Optional notes are
available for each category and for the overall rating, both when adding a game
and when editing its rating. Choose **View rating** to see a game's scores and
notes without opening the editing form. The average overall rating is shown in
the library. Removing a game removes its library entry and associated rating,
but keeps the game record. The SQLite database is created at `instance/project.db`. The
`init-db` command creates a `demo` user with a generated unusable password hash
for development and upgrades the existing category-rating table when needed;
it does not erase existing ratings or notes. Authentication is not implemented
yet. To run the tests:

```powershell
python -m unittest discover -s tests
```

## Run with Docker

Requires Docker with the Compose plugin.

```powershell
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
docker compose up --build -d
```

Open <http://localhost:5000>. Compose initializes the database on startup and
stores it in the persistent `game-data` volume. The app runs as a non-root user
with Waitress. To stop the app while preserving its database:

```powershell
docker compose down
```

Keep the same `SECRET_KEY` value when restarting the app. Do not use the
development fallback secret for a deployed environment.

## Deploy to Google Cloud Run

The Cloud Run deployment uses Cloud SQL for PostgreSQL because container
filesystems are not persistent. You need a Google Cloud project with billing,
a PostgreSQL Cloud SQL instance and database, and a database user. Enable the
Cloud Run, Cloud Build, Artifact Registry, Cloud SQL Admin, and Secret Manager
APIs. Create an Artifact Registry Docker repository in the deployment region.

Create two Secret Manager secrets:

- `game-ratings-secret-key`: a long random secret key.
- `game-ratings-database-url`: the SQLAlchemy URL for the Cloud SQL database,
  using the instance's Cloud SQL connection name as the Unix socket path. For
  example:
  `postgresql+psycopg://APP_USER:URL_ENCODED_PASSWORD@/DATABASE?host=/cloudsql/PROJECT_ID:REGION:INSTANCE_NAME`

Grant the Cloud Run runtime service account `roles/cloudsql.client` and
`roles/secretmanager.secretAccessor` for both secrets. Grant the Cloud Build
service account `roles/run.admin`, `roles/artifactregistry.writer`, and
`roles/iam.serviceAccountUser` so it can build, push, and deploy the service and
initialization job.

Submit a build from PowerShell, replacing the project, region, repository, and
Cloud SQL instance values:

```powershell
gcloud config set project PROJECT_ID
gcloud builds submit --config cloudbuild.yaml --substitutions=_REGION=us-central1,_REPOSITORY=game-ratings,_SERVICE=game-ratings,_INSTANCE_CONNECTION_NAME=PROJECT_ID:us-central1:INSTANCE_NAME,_DATABASE_URL_SECRET=game-ratings-database-url,_SECRET_KEY_SECRET=game-ratings-secret-key
```

The build publishes the image, runs the database initialization job, then
deploys the web service to Cloud Run. It creates a publicly reachable URL;
authentication is not implemented, so use only demo data and do not store
private information. This initializes a PostgreSQL database; it does not
migrate data from a local SQLite database. Cloud Run schema changes after
initial setup will require database migrations; `init-db` creates missing
tables but does not alter existing PostgreSQL tables.

The app factory and database extension live in `app/__init__.py`; starter data
models are in `app/models.py`. `init-db` creates the tables and can be run again
if needed. It does not erase existing data. The default secret key is for local
development only; set the `SECRET_KEY` environment variable before deploying.

## Tech Stack
- Frontend: HTML + CSS with Flask
- Backend: Python
- Database: SQLite with SQLAlchemy
