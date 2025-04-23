# app/models/position.py

from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base

class Position(Base):
    __tablename__ = "tb_positions"
    
    position_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    position_name = Column(String(255), unique=True, nullable=False)
    
    # ความสัมพันธ์กับตาราง User
    users = relationship("User", back_populates="position")
    
    def __repr__(self):
        return f"<Position(position_id={self.position_id}, position_name='{self.position_name}')>"