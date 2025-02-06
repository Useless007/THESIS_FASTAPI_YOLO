# app/routers/product.py

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
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
    ✅ ดึงคำสั่งซื้อของผู้ใช้ที่ล็อกอินอยู่ (ใช้ email ในการระบุผู้ใช้)
    """
    if not current_user:
        print("❌ Unauthorized access - No current_user")
        return JSONResponse(content={"message": "❌ Unauthorized"}, status_code=401)

    print(f"🔍 Fetching orders for user: {current_user.email}")
    orders = db.query(Order).filter(Order.email == current_user.email).all()

    if not orders:
        print("❌ ไม่พบคำสั่งซื้อของผู้ใช้")
        return JSONResponse(content=[], status_code=200)  # ✅ ส่ง array ว่างแทน 404

    return JSONResponse(content=[{
        "order_id": order.order_id,
        "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "status": order.status,
        "total": order.total,
        "image_path": order.image_path if order.image_path else None  # ✅ เช็ค image_path
    } for order in orders])