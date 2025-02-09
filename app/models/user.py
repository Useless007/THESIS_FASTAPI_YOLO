# app/models/user.py

from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from app.database import Base

class User(Base):
    __tablename__ = 'users'  # ชื่อตารางในฐานข้อมูล
    
    id = Column(Integer, primary_key=True, index=True) 
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="customer")  # customer, employee
    name = Column(String(100), nullable=False)
    # แยกฟิลด์ที่อยู่ให้ละเอียดขึ้น
    address = Column(String(500), nullable=True)  # ที่อยู่บ้านเลขที่/ถนน
    # province = Column(String(100), nullable=True)  # จังหวัด
    # postal_code = Column(String(5), nullable=True)  # รหัสไปรษณีย์
    position = Column(String(50), nullable=True)  # admin, packing staff, preparation staff, executive
    phone = Column(String(10), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=False)
