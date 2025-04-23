# app/models/address.py

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Address(Base):
    __tablename__ = "tb_addresses"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("tb_users.id"), nullable=False)
    house_number = Column(String(255), nullable=True)
    village_no = Column(String(255), nullable=True)
    subdistrict = Column(String(255), nullable=True)
    district = Column(String(255), nullable=True)
    province = Column(String(255), nullable=True)
    postal_code = Column(String(255), nullable=True)
    
    # ความสัมพันธ์กับตาราง User
    user = relationship("User", back_populates="addresses")
    
    def __repr__(self):
        return f"<Address(id={self.id}, user_id={self.user_id}, province='{self.province}')>"