from datetime import datetime, timezone

from app import db

RATING_CATEGORIES = ("Gameplay", "Story", "Graphics", "Music", "Difficulty")


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    library_entries = db.relationship(
        "LibraryEntry", back_populates="user", cascade="all, delete-orphan"
    )


class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    developer = db.Column(db.String(160))

    library_entries = db.relationship(
        "LibraryEntry", back_populates="game", cascade="all, delete-orphan"
    )


class LibraryEntry(db.Model):
    __table_args__ = (
        db.UniqueConstraint("user_id", "game_id", name="uq_library_user_game"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey("game.id"), nullable=False)
    added_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship("User", back_populates="library_entries")
    game = db.relationship("Game", back_populates="library_entries")
    rating = db.relationship(
        "Rating",
        back_populates="library_entry",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    library_entry_id = db.Column(
        db.Integer, db.ForeignKey("library_entry.id"), unique=True, nullable=False
    )
    overall_score = db.Column(db.Float)
    notes = db.Column(db.Text)

    library_entry = db.relationship("LibraryEntry", back_populates="rating")
    criteria = db.relationship(
        "RatingCriterion", back_populates="rating", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.CheckConstraint(
            "overall_score IS NULL OR overall_score BETWEEN 1 AND 10",
            name="ck_rating_overall_score",
        ),
    )


class RatingCriterion(db.Model):
    __table_args__ = (
        db.UniqueConstraint("rating_id", "name", name="uq_rating_criterion_name"),
        db.CheckConstraint(
            "score BETWEEN 1 AND 10", name="ck_rating_criterion_score"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    rating_id = db.Column(db.Integer, db.ForeignKey("rating.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    score = db.Column(db.Integer, nullable=False)

    rating = db.relationship("Rating", back_populates="criteria")
