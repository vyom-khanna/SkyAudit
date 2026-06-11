import os
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://schooltruth:schooltruth@localhost:5432/schooltruth"
)

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    with engine.connect() as conn:
        conn.execute(
            __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS postgis")
        )
        conn.commit()
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
