# app/models/camera.py

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    table_number = Column(Integer, nullable=False)  # โต๊ะที่กล้องใช้งาน
    name = Column(String(100), nullable=False)  # ชื่อของกล้อง
    stream_url = Column(String(255), nullable=False)  # URL สำหรับสตรีมวิดีโอของกล้อง
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)  # พนักงานที่ใช้กล้องนี้

    # เชื่อมโยงกับ User (พนักงานที่ใช้กล้องนี้)
    user = relationship("User", backref="camera")

    def __repr__(self):
        return f"<Camera(id={self.id}, table_number={self.table_number}, name='{self.name}', stream_url='{self.stream_url}')>"
