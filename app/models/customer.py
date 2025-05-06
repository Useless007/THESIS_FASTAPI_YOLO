# app/models/customer.py

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
import typing

if typing.TYPE_CHECKING:
    from .address import Address
    from .order import Order

class Customer(Base):
    __tablename__ = "tb_customers"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=True, default=False)
    
    # ความสัมพันธ์กับตารางอื่น
    addresses = relationship("Address", back_populates="customer")
    orders = relationship("Order", back_populates="customer")
    
    def __repr__(self):
        return f"<Customer(id={self.id}, email='{self.email}')>"