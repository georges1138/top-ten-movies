from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 10", name="ck_movies_rating_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tmdb_id: Mapped[int] = mapped_column(unique=True, nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    original_title: Mapped[str] = mapped_column(nullable=False)
    year: Mapped[int | None] = mapped_column(nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(nullable=True)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    review: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
