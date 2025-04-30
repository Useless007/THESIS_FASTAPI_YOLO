# app/routers/preparation.py

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from app.models.order import Order
from app.models.user import User
from app.database import get_db
from app.services.auth import get_user_with_role_and_position_and_isActive
from fastapi.templating import Jinja2Templates
import json

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(prefix="/preparation", tags=["Preparation Staff"])

# ✅ ดึงคำสั่งซื้อที่มีสถานะ confirmed
@router.get("/orders/confirmed", response_class=JSONResponse)
def get_confirmed_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 3))
):
    # ใช้ joinedload เพื่อโหลดข้อมูล user มาด้วย
    orders = db.query(Order).options(joinedload(Order.user)).filter(Order.status == "confirmed").all()
    return [{
        "id": order.order_id, 
        "email": order.user.email if order.user else None,  # ดึง email จาก user relationship
        "total": order.total, 
        "created_at": order.created_at
    } for order in orders]

# ✅ ดึงรายละเอียดคำสั่งซื้อ
@router.get("/orders/{order_id}", response_class=JSONResponse)
def get_order_details(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 3))
):
    """
    ดึงรายละเอียดคำสั่งซื้อ รวมถึงรายการสินค้า
    """
    # ใช้ joinedload เพื่อโหลดข้อมูล user และ order_items
    order = db.query(Order).options(
        joinedload(Order.user),
        joinedload(Order.order_items)
    ).filter(Order.order_id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="❌ Order not found")

    # ดึงข้อมูลสินค้าจาก order_items relationship
    items = []
    if order.order_items:
        for item in order.order_items:
            items.append({
                "product_id": item.product_id,
                "quantity": item.quantity,
                "price": item.price_at_order,
                "total": item.total_item_price,
                "product_name": item.product.name if item.product else "Unknown"
            })

    return {
        "id": order.order_id,
        "email": order.user.email if order.user else None,
        "total": order.total,
        "created_at": order.created_at,
        "items": items
    }

# ✅ อนุมัติคำสั่งซื้อ
@router.put("/orders/{order_id}/approve", response_class=JSONResponse)
def approve_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 3))
):
    """
    อนุมัติคำสั่งซื้อ (เปลี่ยนสถานะเป็น packing)
    """
    order = db.query(Order).filter(and_(Order.order_id == order_id, Order.status == "confirmed")).first()
    if not order:
        raise HTTPException(status_code=404, detail="❌ Order not found or invalid status")
    order.status = "packing"
    db.commit()
    return {"message": f"✅ Order {order_id} approved successfully"}

# ✅ ยกเลิกคำสั่งซื้อ
@router.put("/orders/{order_id}/cancel", response_class=JSONResponse)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 3))
):
    """
    ยกเลิกคำสั่งซื้อ (เปลี่ยนสถานะเป็น cancelled)
    """
    order = db.query(Order).filter(and_(Order.order_id == order_id, Order.status == "confirmed")).first()
    if not order:
        raise HTTPException(status_code=404, detail="❌ Order not found or invalid status")
    order.status = "cancelled"
    db.commit()
    return {"message": f"✅ Order {order_id} canceled successfully"}