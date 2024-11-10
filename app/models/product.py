# models/product.py

from sqlalchemy import Column, Integer, String, Float
# from sqlalchemy.orm import relationship
from app.database import Base

# โมเดลสำหรับ Product
class Product(Base):
    __tablename__ = 'products'  # ชื่อตารางในฐานข้อมูล

    # กำหนดคอลัมน์ของตาราง
    id = Column(Integer, primary_key=True, index=True)  # id เป็น primary key
    name = Column(String(255), index=True)                    # ชื่อของสินค้า
    description = Column(String(255), nullable=True)          # คำอธิบายสินค้า
    price = Column(Float, nullable=False)                # ราคาสินค้า
    stock = Column(Integer, default=0)                   # จำนวนสินค้าที่มีในสต็อก

    # ความสัมพันธ์กับตารางอื่นๆ ถ้ามี (เช่น Order หรือ Category)
    # order_items = relationship("OrderItem", back_populates="product")
