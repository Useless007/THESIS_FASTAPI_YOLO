# app/models/product.py

from sqlalchemy import Column, Integer, String, Float, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Product(Base):
    __tablename__ = "tb_products"
    
    product_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    description = Column(Text, nullable=False)
    image_path = Column(String(255), nullable=False)
    stock = Column(Integer, default=0)
    
    # ความสัมพันธ์กับตาราง OrderItem
    order_items = relationship("OrderItem", back_populates="product")
    
    def __repr__(self):
        return f"<Product(product_id={self.product_id}, name='{self.name}', price={self.price}, stock={self.stock})>"