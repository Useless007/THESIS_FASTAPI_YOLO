# app/models/order.py

from sqlalchemy import Column, Integer, String, Float, DateTime, Text
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
    slip_path = Column(String(255), nullable=True)  # เพิ่มฟิลด์นี้เพื่อเก็บ path ของสลิปการโอนเงิน
