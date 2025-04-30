# app/schemas/camera.py

from pydantic import BaseModel
from typing import Optional

class CameraBase(BaseModel):
    name: str
    stream_url: str
    assigned_to: Optional[int] = None

class CameraCreate(CameraBase):
    pass

class CameraUpdate(BaseModel):
    name: Optional[str] = None
    stream_url: Optional[str] = None
    assigned_to: Optional[int] = None

class Camera(CameraBase):
    id: int
    
    class Config:
        orm_mode = True  # สำหรับ Pydantic v1