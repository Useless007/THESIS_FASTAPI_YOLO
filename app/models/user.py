# app/models/user.py

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base
import typing

if typing.TYPE_CHECKING:
    from .role import Role
    from .position import Position
    from .order import Order
    from .camera import Camera
    from .address import Address
    from .account import Account

class User(Base):
    __tablename__ = "tb_users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("tb_accounts.id"), nullable=False, unique=True)
    role_id = Column(Integer, ForeignKey("tb_roles.role_id"), nullable=False)
    position_id = Column(Integer, ForeignKey("tb_positions.position_id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=True)
    
    # ความสัมพันธ์กับตารางอื่น
    account = relationship("Account", back_populates="user")
    role = relationship("Role", back_populates="users")
    position = relationship("Position", back_populates="users")
    assigned_orders = relationship("Order", foreign_keys="Order.assigned_to", back_populates="assigned_user")
    cameras = relationship("Camera", back_populates="assigned_user")
    addresses = relationship("Address", back_populates="user", foreign_keys="Address.user_id")
    
    def __repr__(self):
        return f"<User(id={self.id}, account_id={self.account_id}, role_id={self.role_id}, position_id={self.position_id})>"
    
    @property
    def email(self):
        """Get the user's email from the associated account"""
        return self.account.email if self.account else None
    
    @property
    def name(self):
        """Get the user's name from the associated account"""
        return self.account.name if self.account else None
    
    @property
    def phone(self):
        """Get the user's phone from the associated account"""
        return self.account.phone if self.account else None
    
    @property
    def password(self):
        """Get the user's password from the associated account"""
        return self.account.password if self.account else None
    
    @property
    def is_active(self):
        """Get the user's active status from the associated account"""
        return self.account.is_active if self.account else False
    
    @property
    def is_employee(self):
        """Check if this user is an employee"""
        from .role import Role
        return self.role_id == Role.get_employee_role_id()
    
    @property
    def is_admin(self):
        """Check if this user is an admin"""
        from .role import Role
        return self.role_id == Role.get_admin_role_id()
    
    @property
    def is_executive(self):
        """Check if this user is an executive"""
        from .role import Role
        return self.role_id == Role.get_executive_role_id()