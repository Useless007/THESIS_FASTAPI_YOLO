# app/schemas/order_status_log.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class OrderStatusLogBase(BaseModel):
    order_id: int
    old_status: str
    new_status: str
    reason: Optional[str] = None
    changed_by: int

class OrderStatusLogCreate(OrderStatusLogBase):
    pass

class OrderStatusLogUpdate(BaseModel):
    reason: Optional[str] = None

class OrderStatusLog(OrderStatusLogBase):
    id: int
    created_at: datetime
    changed_by_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class OrderStatusRevertRequest(BaseModel):
    order_id: int
    reason: str
    
    class Config:
        from_attributes = True
