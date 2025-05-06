# app/models/role.py

from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base

class Role(Base):
    __tablename__ = "tb_roles"
    
    role_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role_name = Column(String(255), unique=True, nullable=False)
    
    # ความสัมพันธ์กับตาราง User (เฉพาะพนักงาน)
    users = relationship("User", back_populates="role")
    
    def __repr__(self):
        return f"<Role(role_id={self.role_id}, role_name='{self.role_name}')>"

    @classmethod
    def get_employee_role_id(cls):
        """Return role ID for employee"""
        return 1
        
    @classmethod
    def get_admin_role_id(cls):
        """Return role ID for admin"""
        return 2
        
    @classmethod
    def get_executive_role_id(cls):
        """Return role ID for executive"""
        return 3