# app/schemas/order.py

from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class OrderItemBase(BaseModel):
    product_id: int
    quantity: int
    price_at_order: float
    total_item_price: float

class OrderItemCreate(OrderItemBase):
    pass

    class Config:
        from_attributes = True

class OrderItemOut(OrderItemBase):
    item_id: int
    order_id: int

    class Config:
        from_attributes = True

class OrderItemWithProduct(OrderItemOut):
    product: 'ProductOut'

    class Config:
        from_attributes = True

class OrderBase(BaseModel):
    user_id: int
    total: float
    status: str = "pending"
    slip_path: Optional[str] = None
    image_path: Optional[str] = None
    
class OrderCreate(OrderBase):
    created_at: datetime = datetime.utcnow()
    
    class Config:
        from_attributes = True

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[int] = None
    camera_id: Optional[int] = None
    is_verified: Optional[bool] = None
    image_path: Optional[str] = None
    updated_at: datetime = datetime.utcnow()

    class Config:
        from_attributes = True

class OrderOut(BaseModel):
    order_id: int
    user_id: int
    total: float
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    slip_path: Optional[str] = None
    assigned_to: Optional[int] = None
    camera_id: Optional[int] = None
    is_verified: bool
    image_path: Optional[str] = None
    order_items: List[OrderItemOut] = []

    class Config:
        from_attributes = True

class OrderWithDetails(OrderOut):
    user: 'UserBase'
    assigned_user: Optional['UserBase'] = None
    camera: Optional['CameraBase'] = None
    order_items: List[OrderItemWithProduct] = []

    class Config:
        from_attributes = True

class VerifyRequest(BaseModel):
    verified: bool

class DetectFromCameraRequest(BaseModel):
    camera_id: int
    order_id: int

from app.schemas.product import ProductOut
from app.schemas.user import UserBase
from app.schemas.camera import CameraBase

OrderItemWithProduct.update_forward_refs()
OrderWithDetails.update_forward_refs()