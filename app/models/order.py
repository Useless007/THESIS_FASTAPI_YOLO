# app/models/order.py

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Order(Base):
    __tablename__ = "orders"

    order_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(100), nullable=False)
    item = Column(Text, nullable=False)  # เก็บ JSON หรือ Text
    total = Column(Float, nullable=False)
    status = Column(String(10), default="pending")  # pending, cancelled, confirmed, packing, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    slip_path = Column(String(255), nullable=True)  # เก็บ path ของสลิปการโอนเงิน

    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)  # พนักงานที่รับออเดอร์นี้
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)  # กล้องที่ใช้ถ่ายออเดอร์นี้

    # เชื่อมโยงกับ User และ Camera
    user = relationship("User", backref="orders")
    camera = relationship("Camera", backref="orders")

    def __repr__(self):
        return f"<Order(order_id={self.order_id}, status='{self.status}', assigned_to={self.assigned_to}, camera_id={self.camera_id})>"
