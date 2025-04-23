# app/models/order.py

from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Order(Base):
    __tablename__ = "tb_orders"
    
    order_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("tb_users.id"), nullable=False)
    total = Column(Float, nullable=False)
    status = Column(String(255), default="pending", nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    slip_path = Column(String(255), nullable=True)
    assigned_to = Column(Integer, ForeignKey("tb_users.id"), nullable=True)
    camera_id = Column(Integer, ForeignKey("tb_cameras.id"), nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    image_path = Column(String(255), nullable=True)
    
    # ความสัมพันธ์กับตารางอื่น
    user = relationship("User", foreign_keys=[user_id], back_populates="orders")
    assigned_user = relationship("User", foreign_keys=[assigned_to], back_populates="assigned_orders")
    camera = relationship("Camera", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Order(order_id={self.order_id}, user_id={self.user_id}, status='{self.status}', total={self.total})>"