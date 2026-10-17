import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def database_url():
    required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError("Missing database settings: " + ", ".join(missing) + ". Copy .env.example to .env and configure it.")
    from sqlalchemy.engine import URL

    try:
        port = int(os.getenv("DB_PORT", "3306"))
    except ValueError:
        raise RuntimeError("DB_PORT must be a number between 1 and 65535.") from None
    if not 1 <= port <= 65535:
        raise RuntimeError("DB_PORT must be a number between 1 and 65535.")

    return URL.create(
        "mysql+pymysql",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=port,
        database=os.environ["DB_NAME"],
    )

required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
engine = (
    create_engine(
        database_url(),
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
    if all(os.getenv(key) for key in required)
    else None
)
SessionLocal = sessionmaker(bind=engine) if engine is not None else None
