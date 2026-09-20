import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Fallback to sqlite if postgres is not accessible for local testing
_base_dir = os.path.dirname(os.path.abspath(__file__))
_default_db_path = os.path.join(_base_dir, "meredian.db").replace("\\", "/")

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    f"sqlite:///{_default_db_path}"
)

# For SQLite, we need check_same_thread=False
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
