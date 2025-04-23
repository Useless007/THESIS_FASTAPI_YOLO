# app/models/role.py

from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base

class Role(Base):
    __tablename__ = "tb_roles"
    
    role_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role_name = Column(String(255), unique=True, nullable=False)
    
    # ความสัมพันธ์กับตาราง User
    users = relationship("User", back_populates="role")
    
    def __repr__(self):
        return f"<Role(role_id={self.role_id}, role_name='{self.role_name}')>"