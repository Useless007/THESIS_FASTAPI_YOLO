# models/customer.py

from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from app.database import Base

# โมเดลสำหรับ Customer
class Customer(Base):
    __tablename__ = 'customers' # ชื่อตารางในฐานข้อมูล
    
    id = Column(Integer, primary_key=True, index=True) # id เป็น primary key
    username = Column(String(255), unique=True, index=True) # ชื่อผู้ใช้ของลูกค้า
    email = Column(String(255), unique=True, index=True, nullable=False) # อีเมลของลูกค้า
    password = Column(String(255), nullable=False) # รหัสผ่านของลูกค้า
    name = Column(String(255), nullable=False) # ชื่อของลูกค้า
    address = Column(String(255), nullable=True)  # ข้อมูลที่อยู่เฉพาะสำหรับลูกค้า
    phone = Column(String(10), nullable=True) # เบอร์โทรศัพท์ของลูกค้า
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # วันที่เวลาที่สร้างข้อมูล
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) # วันที่เวลาที่แก้ไขข้อมูล
    is_active = Column(Boolean, default=True) # สถานะการใช้งานของลูกค้า