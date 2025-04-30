# app/schemas/address.py

from pydantic import BaseModel
from typing import Optional

class AddressBase(BaseModel):
    house_number: Optional[str] = None
    village_no: Optional[str] = None
    subdistrict: Optional[str] = None
    district: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None

class AddressCreate(AddressBase):
    user_id: int

    class Config:
        from_attributes = True

class AddressUpdate(AddressBase):
    pass

    class Config:
        from_attributes = True

class Address(AddressBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True