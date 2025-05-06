# app/models/account.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base
import datetime
import typing

if typing.TYPE_CHECKING:
    from .user import User
    from .customer import Customer

class Account(Base):
    """
    โมเดลตาราง Account เป็นตารางกลางสำหรับการเก็บข้อมูลผู้ใช้ทั้งหมด
    ทั้ง User (พนักงาน) และ Customer (ลูกค้า) จะเชื่อมโยงกับตารางนี้
    """
    __tablename__ = "tb_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # ความสัมพันธ์กับตารางอื่น
    user = relationship("User", back_populates="account", uselist=False)
    customer = relationship("Customer", back_populates="account", uselist=False)
    
    def __repr__(self):
        return f"<Account(id={self.id}, email='{self.email}', name='{self.name}', is_active={self.is_active})>"