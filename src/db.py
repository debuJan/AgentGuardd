import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    # NOTE: the +psycopg dialect matches the pinned psycopg[binary] (v3)
    # dependency. Do not switch this back to psycopg2: it is not installed.
    "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/agentguard",
)

# Render and Heroku expose Postgres as "postgres://..."; SQLAlchemy 2.x only
# accepts "postgresql://...". Normalize the scheme (and dialect) here so the
# same code runs on PaaS without a DATABASE_URL rewrite.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)