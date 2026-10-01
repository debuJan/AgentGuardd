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

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)