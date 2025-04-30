# app/schemas/product.py

from pydantic import BaseModel
from typing import Optional

class ProductBase(BaseModel):
    name: str
    price: float
    description: str
    image_path: str

class ProductCreate(ProductBase):
    pass

    class Config:
        from_attributes = True

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    image_path: Optional[str] = None

    class Config:
        from_attributes = True

class ProductOut(ProductBase):
    product_id: int

    class Config:
        from_attributes = True

class ProductWithCategory(ProductOut):
    category: Optional[str] = None  # สำหรับแสดงหมวดหมู่ที่ได้จาก utils

    class Config:
        from_attributes = True