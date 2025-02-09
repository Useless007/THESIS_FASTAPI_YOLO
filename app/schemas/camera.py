from pydantic import BaseModel
from typing import Optional

class UserBase(BaseModel):
    id: int
    name: str
    
    class Config:
        orm_mode = True

class CameraBase(BaseModel):
    table_number: int
    name: str
    stream_url: str
    assigned_to: Optional[int] = None

    class Config:
        orm_mode = True

class CameraCreate(CameraBase):
    pass

class CameraUpdate(BaseModel):
    table_number: Optional[int] = None
    name: Optional[str] = None
    stream_url: Optional[str] = None
    assigned_to: Optional[int] = None

    class Config:
        orm_mode = True

class Camera(CameraBase):
    id: int
    user: Optional[UserBase] = None

    class Config:
        orm_mode = True
