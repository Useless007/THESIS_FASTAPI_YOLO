# app/schemas/user.py

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Schema สำหรับการสร้าง User
class UserCreate(BaseModel):
    # username: str
    email: str
    password: str
    name: str
    role: str
    address: Optional[str] = None
    position: Optional[str] = None
    phone: Optional[str] = None

    class Config:
        orm_mode = True

# Schema สำหรับการอัปเดต User
class UserUpdate(BaseModel):
    # username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    address: Optional[str] = None
    position: Optional[str] = None
    phone: Optional[str] = None

    class Config:
        orm_mode = True

# Schema สำหรับการแสดงข้อมูล User
class UserOut(BaseModel):
    id: int
    # username: str
    email: str
    name: str
    role: str
    address: Optional[str] = None
    position: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: bool

    class Config:
        orm_mode = True
