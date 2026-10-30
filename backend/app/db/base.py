"""SQLAlchemy declarative Base.

OWNER: Shubham

All ORM models are owned by Shubham. No models exist in Phase 0.
Once models are created, import them in alembic/env.py so that
`alembic revision --autogenerate` can detect them.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()

