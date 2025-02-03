# app/routers/product.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.product import ProductCreate, ProductUpdate, ProductOut
from app.schemas.order import OrderOut
from app.models.order import Order
from app.services.auth import get_current_user

order_router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
)

@order_router.get("/my-orders", response_model=list[OrderOut])
def get_my_orders(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    ดึงคำสั่งซื้อของผู้ใช้ที่ล็อกอินอยู่ (ใช้ email ในการระบุผู้ใช้)
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="❌ Unauthorized")

    orders = db.query(Order).filter(Order.email == current_user.email).all()

    if not orders:
        raise HTTPException(status_code=404, detail="❌ ไม่พบคำสั่งซื้อของคุณ")

    return orders