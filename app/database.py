# app/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker,declarative_base
from .config import settings

# SQLAlchemy database URL สำหรับ MySQL
SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{settings.DATABASE_USERNAME}:{settings.DATABASE_PASSWORD}@"
    f"{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
)

# สร้าง Engine และ Session สำหรับ MySQL
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# กำหนด Base สำหรับการสร้างโมเดล
Base = declarative_base()

# Dependency ที่ใช้เรียก SessionLocal ในแต่ละ request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
