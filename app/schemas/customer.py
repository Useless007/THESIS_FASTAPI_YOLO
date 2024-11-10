# schemas/customer.py

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Schema สำหรับการสร้างข้อมูล Customer
class CustomerCreate(BaseModel):
    username: str
    email: str
    password: str
    name: str
    address: Optional[str] = None  # ข้อมูลที่อยู่ (สามารถไม่ใส่ได้)
    phone: Optional[str] = None     # เบอร์โทรศัพท์ (สามารถไม่ใส่ได้)

    class Config:
        orm_mode = True  # ทำให้ Pydantic ใช้งานกับ SQLAlchemy models ได้

# Schema สำหรับการอัปเดตข้อมูล Customer
class CustomerUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None

    class Config:
        orm_mode = True  # ทำให้ Pydantic ใช้งานกับ SQLAlchemy models ได้

# Schema สำหรับการแสดงข้อมูล Customer (สำหรับดึงข้อมูลจาก DB)
class CustomerOut(BaseModel):
    id: int
    username: str
    email: str
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: bool

    class Config:
        orm_mode = True  # ทำให้ Pydantic ใช้งานกับ SQLAlchemy models ได้
