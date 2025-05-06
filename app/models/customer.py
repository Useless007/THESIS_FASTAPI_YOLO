# app/models/customer.py

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base
import typing

if typing.TYPE_CHECKING:
    from .address import Address
    from .order import Order
    from .account import Account

class Customer(Base):
    __tablename__ = "tb_customers"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("tb_accounts.id"), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=True)
    
    # ความสัมพันธ์กับตารางอื่น
    account = relationship("Account", back_populates="customer")
    orders = relationship("Order", back_populates="customer", foreign_keys="Order.customer_id")
    addresses = relationship("Address", back_populates="customer", foreign_keys="Address.customer_id")
    
    def __repr__(self):
        return f"<Customer(id={self.id}, account_id={self.account_id})>"
    
    @property
    def email(self):
        """Get the customer's email from the associated account"""
        return self.account.email if self.account else None
    
    @property
    def name(self):
        """Get the customer's name from the associated account"""
        return self.account.name if self.account else None
    
    @property
    def phone(self):
        """Get the customer's phone from the associated account"""
        return self.account.phone if self.account else None
    
    @property
    def password(self):
        """Get the customer's password from the associated account"""
        return self.account.password if self.account else None
    
    @property
    def is_active(self):
        """Get the customer's active status from the associated account"""
        return self.account.is_active if self.account else False