# test/dbtest.py

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
from app.database import Base, get_db
from app.config import settings

# นำเข้าโมเดลที่ต้องการทดสอบ
from app.models.customer import Customer  
from app.models.product import Product

# Database URL สำหรับการทดสอบ (ควรเป็นฐานข้อมูลแยกเฉพาะสำหรับการทดสอบ)
TEST_SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{settings.DATABASE_USERNAME}:{settings.DATABASE_PASSWORD}@"
    f"{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}_test"
)

# สร้าง Engine และ Session สำหรับการทดสอบ
engine = create_engine(TEST_SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# สร้างและลบตารางในฐานข้อมูลการทดสอบก่อนและหลังการรันเทส
@pytest.fixture(scope="session", autouse=True)
def setup_database():
    # สร้างตารางจากโมเดล
    Base.metadata.create_all(bind=engine)
    yield
    # ลบตารางเมื่อเสร็จสิ้นการทดสอบ
    Base.metadata.drop_all(bind=engine)

# Dependency ใหม่ที่ใช้กับการทดสอบ
@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# ตัวอย่างการทดสอบการเชื่อมต่อและการเพิ่มข้อมูล
def test_database_connection(db_session):
    # ใช้ text() เพื่อระบุคำสั่ง SQL
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1

# ตัวอย่างการทดสอบ CRUD เบื้องต้น (อาจต้องสร้างโมเดลที่ใช้งานจริงในระบบ)
def test_create_and_query_customer(db_session):
    # ตัวอย่างโค้ด: เพิ่มข้อมูลลูกค้าใหม่ในฐานข้อมูล
    from app.models.customer import Customer  # แก้ไขให้ตรงกับชื่อไฟล์และโมเดลของคุณ
    new_customer = Customer(name="Test Customer", email="test@example.com")
    
    db_session.add(new_customer)
    db_session.commit()
    db_session.refresh(new_customer)
    
    # ตรวจสอบว่าลูกค้าถูกสร้างในฐานข้อมูล
    queried_customer = db_session.query(Customer).filter_by(email="test@example.com").first()
    assert queried_customer is not None
    assert queried_customer.name == "Test Customer"
