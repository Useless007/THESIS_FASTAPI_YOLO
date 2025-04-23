# app/models/user.py

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base
import typing

if typing.TYPE_CHECKING:
    from .role import Role
    from .position import Position
    from .address import Address
    from .order import Order
    from .camera import Camera

class User(Base):
    __tablename__ = "tb_users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("tb_roles.role_id"), nullable=False)
    position_id = Column(Integer, ForeignKey("tb_positions.position_id"), nullable=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=True)
    
    # ความสัมพันธ์กับตารางอื่น - ใช้ string reference แทน direct class
    role = relationship("Role", back_populates="users")
    position = relationship("Position", back_populates="users")
    addresses = relationship("Address", back_populates="user")
    orders = relationship("Order", foreign_keys="Order.user_id", back_populates="user")
    assigned_orders = relationship("Order", foreign_keys="Order.assigned_to", back_populates="assigned_user")
    cameras = relationship("Camera", back_populates="assigned_user")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role_id={self.role_id}, position_id={self.position_id})>"