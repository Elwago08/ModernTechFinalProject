import os

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash
from secrets import token_urlsafe

db = SQLAlchemy()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "development-only-change-me"),
        SQLALCHEMY_DATABASE_URI="sqlite:///project.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)

    from app import models  # noqa: F401

    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        from app.models import User

        demo_user = User.query.filter_by(username="demo").first()
        if demo_user is None:
            db.session.add(
                User(
                    username="demo",
                    email="demo@example.test",
                    password_hash=generate_password_hash(token_urlsafe(32)),
                )
            )
            db.session.commit()
        print("Initialized the database.")

    @app.get("/")
    def index():
        from app.models import LibraryEntry, User

        demo_user = User.query.filter_by(username="demo").first()
        if demo_user is None:
            return "Database not initialized. Run `flask --app run.py init-db`.", 503

        library_entries = (
            LibraryEntry.query.filter_by(user_id=demo_user.id)
            .order_by(LibraryEntry.added_at.desc())
            .all()
        )
        return render_template("index.html", library_entries=library_entries)

    @app.post("/library/add")
    def add_game():
        from app.models import Game, LibraryEntry, User

        title = request.form.get("title", "").strip()
        if not title:
            flash("Enter a game name to add it to your library.", "error")
            return redirect(url_for("index"))
        if len(title) > 200:
            flash("Game names must be 200 characters or fewer.", "error")
            return redirect(url_for("index"))

        demo_user = User.query.filter_by(username="demo").first()
        if demo_user is None:
            return "Database not initialized. Run `flask --app run.py init-db`.", 503

        game = Game.query.filter(func.lower(Game.title) == title.lower()).first()
        if game is None:
            game = Game(title=title)
            db.session.add(game)
            db.session.flush()

        existing_entry = LibraryEntry.query.filter_by(
            user_id=demo_user.id, game_id=game.id
        ).first()
        if existing_entry is not None:
            flash(f"{game.title} is already in your library.", "info")
            return redirect(url_for("index"))

        db.session.add(LibraryEntry(user=demo_user, game=game))
        db.session.commit()
        flash(f"Added {game.title} to your library.", "success")
        return redirect(url_for("index"))

    return app
