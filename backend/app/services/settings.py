"""Reads of the small settings table shared by several modules."""

from sqlalchemy.orm import Session

from app.models import Setting

DEFAULT_WEAK_THRESHOLD = 60


def weak_threshold(db: Session) -> int:
    """Percent below which a topic counts as weak (Admin can change it). Always 1 to 100."""
    row = db.get(Setting, "weak_topic_threshold")
    try:
        return max(1, min(100, int(row.value))) if row else DEFAULT_WEAK_THRESHOLD
    except ValueError:
        return DEFAULT_WEAK_THRESHOLD
