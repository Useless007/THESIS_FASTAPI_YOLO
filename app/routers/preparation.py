# app/routers/praparation.py

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.orm import Session
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
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "preparation staff"))
):
    orders = db.query(Order).filter(Order.status == "confirmed").all()
    return [{"id": order.order_id, "email": order.email, "total": order.total, "created_at": order.created_at} for order in orders]

# ✅ ดึงรายละเอียดคำสั่งซื้อ
@router.get("/orders/{order_id}", response_class=JSONResponse)
def get_order_details(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "preparation staff"))
):
    """
    ดึงรายละเอียดคำสั่งซื้อ รวมถึงรายการสินค้า
    """
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="❌ Order not found")

    try:
        items = json.loads(order.item) if order.item else []
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="❌ Invalid JSON format in order items")

    return {
        "id": order.order_id,
        "email": order.email,
        "total": order.total,
        "created_at": order.created_at,
        "items": items
    }

# ✅ อนุมัติคำสั่งซื้อ
@router.put("/orders/{order_id}/approve", response_class=JSONResponse)
def approve_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "preparation staff"))
):
    """
    อนุมัติคำสั่งซื้อ (เปลี่ยนสถานะเป็น ready_for_packing)
    """
    order = db.query(Order).filter(and_(Order.order_id == order_id, Order.status == "confirmed")).first()
    if not order:
        raise HTTPException(status_code=404, detail="❌ Order not found or invalid status")
    order.status = "ready_for_packing"
    db.commit()
    return {"message": f"✅ Order {order_id} approved successfully"}

# ✅ ยกเลิกคำสั่งซื้อ
@router.put("/orders/{order_id}/cancel", response_class=JSONResponse)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "preparation staff"))
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
