from pydantic import BaseModel
from datetime import datetime
from typing import List

class OrderOut(BaseModel):
    order_id: int  # ต้องตรงกับคอลัมน์ order_id ในตาราง
    email: str
    item: str
    total: float
    status: str
    created_at: datetime
    slip_path: str
    assigned_to: int

    class Config:
        orm_mode = True
