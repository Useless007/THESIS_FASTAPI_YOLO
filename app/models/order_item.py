# app/models/order_item.py

from sqlalchemy import Column, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class OrderItem(Base):
    __tablename__ = "tb_order_items"
    
    item_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("tb_orders.order_id"), nullable=False)
    product_id = Column(Integer, ForeignKey("tb_products.product_id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price_at_order = Column(Float, nullable=False)
    total_item_price = Column(Float, nullable=False)
    
    # ความสัมพันธ์กับตารางอื่น
    order = relationship("Order", back_populates="order_items")
    product = relationship("Product", back_populates="order_items")
    
    def __repr__(self):
        return f"<OrderItem(item_id={self.item_id}, order_id={self.order_id}, product_id={self.product_id}, quantity={self.quantity})>"