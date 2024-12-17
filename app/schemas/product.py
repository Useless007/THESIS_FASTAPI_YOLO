# app/schemas/product.py

from pydantic import BaseModel
from typing import Optional

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock: int

    class Config:
        orm_mode = True

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None

    class Config:
        orm_mode = True

class ProductOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    stock: int

    class Config:
        orm_mode = True