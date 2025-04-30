# app/schemas/role_position.py

from pydantic import BaseModel
from typing import Optional

class RoleBase(BaseModel):
    role_name: str

class RoleCreate(RoleBase):
    pass

    class Config:
        from_attributes = True

class RoleOut(RoleBase):
    role_id: int

    class Config:
        from_attributes = True

class PositionBase(BaseModel):
    position_name: str

class PositionCreate(PositionBase):
    pass

    class Config:
        from_attributes = True

class PositionOut(PositionBase):
    position_id: int

    class Config:
        from_attributes = True