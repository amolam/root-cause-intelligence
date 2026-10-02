import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.db.config import get_settings

# Vercel can keep several warm function instances alive, and each SQLAlchemy
# QueuePool may retain idle PostgreSQL connections between requests. On
# serverless, close each connection when its request session ends so warm
# instances do not reserve Aiven's limited connection slots while idle.
if os.getenv("VERCEL"):
    engine = create_engine(get_settings().sqlalchemy_url(), poolclass=NullPool, pool_pre_ping=True)
else:
    engine = create_engine(get_settings().sqlalchemy_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
