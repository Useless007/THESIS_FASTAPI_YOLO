# app/models/camera.py

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Camera(Base):
    __tablename__ = "tb_cameras"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    stream_url = Column(String(255), nullable=False)
    assigned_to = Column(Integer, ForeignKey("tb_users.id"), nullable=True)
    
    # ความสัมพันธ์กับตารางอื่น
    assigned_user = relationship("User", back_populates="cameras")
    orders = relationship("Order", back_populates="camera")
    
    def __repr__(self):
        return f"<Camera(id={self.id}, name='{self.name}', assigned_to={self.assigned_to})>"