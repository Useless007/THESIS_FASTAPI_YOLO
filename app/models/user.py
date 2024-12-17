# app/models/user.py

from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from app.database import Base

class User(Base):
    __tablename__ = 'users' # ชื่อตารางในฐานข้อมูล
    
    id = Column(Integer, primary_key=True, index=True) 
    username = Column(String(255), unique=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="customer")  # ระบุบทบาทเช่น customer, admin, packaging_staff, etc.
    name = Column(String(255), nullable=False)
    address = Column(String(255), nullable=True)  # ใช้เฉพาะกับ customer
    position = Column(String(50), nullable=True)  # ใช้เฉพาะกับ employee
    phone = Column(String(10), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=False)
