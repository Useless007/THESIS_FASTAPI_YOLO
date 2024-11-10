# models/employee.py

from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from app.database import Base

# โมเดลสำหรับ Employee
class Employee(Base):
    __tablename__ = 'employees' # ชื่อตารางในฐานข้อมูล
    
    id = Column(Integer, primary_key=True, index=True) # id เป็น primary key
    username = Column(String(255), unique=True, index=True) # ชื่อผู้ใช้ของพนักงาน
    email = Column(String(255), unique=True, index=True, nullable=False) # อีเมลของพนักงาน
    password = Column(String(255), nullable=False) # รหัสผ่านของพนักงาน
    role = Column(String(50), default="staff")  # อาจใช้ role แยกประเภทพนักงาน (staff, admin)
    position = Column(String(50), nullable=True)  # ตำแหน่งงานเฉพาะของพนักงาน
    phone = Column(String(10), nullable=True) # เบอร์โทรศัพท์ของพนักงาน
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # วันที่เวลาที่สร้างข้อมูล
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) # วันที่เวลาที่แก้ไขข้อมูล
    is_active = Column(Boolean, default=True) # สถานะการใช้งานของพนักงาน