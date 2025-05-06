# app/schemas/customer.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

class CustomerBase(BaseModel):
    id: int
    email: str
    name: str

    class Config:
        from_attributes = True

class CustomerCreate(BaseModel):
    email: str
    password: str
    name: str
    phone: Optional[str] = None
    is_active: bool = Field(default=False)

    class Config:
        from_attributes = True

class CustomerUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

    class Config:
        from_attributes = True

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

class CustomerOut(BaseModel):
    id: int
    email: str
    name: str
    phone: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    addresses: List[AddressBase] = []

    class Config:
        from_attributes = True