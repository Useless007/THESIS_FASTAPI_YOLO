# app/schemas/user.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    id: int
    email: str
    name: str

    class Config:
        from_attributes = True

# Schema สำหรับการสร้าง User
class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    role_id: int = Field(default=2)  # Default เป็น customer (role_id: 2)
    position_id: Optional[int] = None
    phone: Optional[str] = None
    is_active: bool = Field(default=False)

    class Config:
        from_attributes = True

# Schema สำหรับการอัปเดต User
class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    role_id: Optional[int] = None
    position_id: Optional[int] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

    class Config:
        from_attributes = True

# Schema สำหรับ Role กับ Position ที่จะแสดงร่วมกับ User
class RoleBase(BaseModel):
    role_id: int
    role_name: str

    class Config:
        from_attributes = True

class PositionBase(BaseModel):
    position_id: int
    position_name: str

    class Config:
        from_attributes = True

# Schema สำหรับที่อยู่
class AddressBase(BaseModel):
    id: int
    house_number: Optional[str] = None
    village_no: Optional[str] = None
    subdistrict: Optional[str] = None
    district: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None

    class Config:
        from_attributes = True

# Schema สำหรับการแสดงข้อมูล User
class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: RoleBase
    position: Optional[PositionBase] = None
    phone: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    addresses: List[AddressBase] = []

    class Config:
        from_attributes = True

# Schema สำหรับ Authentication
class TokenData(BaseModel):
    email: Optional[str] = None