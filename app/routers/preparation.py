# app/routers/preparation.py

from fastapi import APIRouter, Depends, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from app.models.order import Order
from app.models.user import User
from app.models.product import Product  # เพิ่ม import Product
from app.database import get_db
from app.services.auth import get_user_with_role_and_position_and_isActive
from fastapi.templating import Jinja2Templates
from app.services.ws_manager import preparation_connections
import json
from app.utils.product_categories import get_product_category  # เพิ่ม import get_product_category

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(prefix="/preparation", tags=["Preparation Staff"])

# ✅ ดึงคำสั่งซื้อที่มีสถานะ confirmed
@router.get("/orders/confirmed", response_class=JSONResponse)
def get_confirmed_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 3))
):
    # ใช้ joinedload เพื่อโหลดข้อมูล customer มาด้วย (แก้จาก user เป็น customer)
    orders = db.query(Order).options(joinedload(Order.customer)).filter(Order.status == "confirmed").all()
    return [{
        "id": order.order_id, 
        "email": order.customer.email if order.customer else None,  # แก้จาก user เป็น customer
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
    # ใช้ joinedload เพื่อโหลดข้อมูล customer และ order_items
    order = db.query(Order).options(
        joinedload(Order.customer),
        joinedload(Order.order_items)
    ).filter(Order.order_id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="❌ Order not found")

    # ดึงข้อมูลสินค้าจาก order_items relationship
    items = []
    if order.order_items:
        for item in order.order_items:
            # Get product info including the image path
            product_info = {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "price": item.price_at_order,
                "total": item.total_item_price,
                "product_name": item.product.name if item.product else "Unknown"
            }
            
            # Add image path if product exists
            if item.product:
                product_info["image_path"] = item.product.image_path
                
            items.append(product_info)

    return {
        "id": order.order_id,
        "email": order.customer.email if order.customer else None,
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
    อนุมัติคำสั่งซื้อ (เปลี่ยนสถานะเป็น packing) และอัพเดตจำนวนสินค้าคงเหลือ
    """
    # ใช้ joinedload เพื่อโหลดข้อมูล order_items
    order = db.query(Order).options(joinedload(Order.order_items)).filter(
        and_(Order.order_id == order_id, Order.status == "confirmed")
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="❌ Order not found or invalid status")
    
    # ตรวจสอบและอัพเดตสต็อกสินค้า
    insufficient_stock = []
    from app.models.product import Product
    
    # เก็บข้อมูลสินค้าที่ต้องอัพเดต
    products_to_update = []
    
    for item in order.order_items:
        product = db.query(Product).filter(Product.product_id == item.product_id).first()
        if not product:
            continue
            
        # ตรวจสอบว่าสินค้ามีเพียงพอหรือไม่
        if product.stock < item.quantity:
            insufficient_stock.append({
                "product_name": product.name,
                "requested": item.quantity,
                "available": product.stock
            })
        else:
            # เก็บข้อมูลสินค้าที่จะอัพเดต
            products_to_update.append({
                "product": product,
                "quantity": item.quantity
            })
    
    # ถ้ามีสินค้าไม่เพียงพอ ให้แจ้งเตือน
    if insufficient_stock:
        return JSONResponse(
            status_code=400,
            content={
                "message": "❌ สินค้าในคลังไม่เพียงพอ",
                "insufficient_items": insufficient_stock
            }
        )
    
    # ถ้าสินค้าเพียงพอ ให้อัพเดตสต็อกและเปลี่ยนสถานะออเดอร์
    for item in products_to_update:
        item["product"].stock -= item["quantity"]
    
    # เปลี่ยนสถานะออเดอร์เป็น packing
    order.status = "packing"
    # order.assigned_to = current_user.id  # บันทึกว่าใครเป็นคนยืนยันออเดอร์นี้
    
    db.commit()
    return {"message": f"✅ Order {order_id} approved successfully and stock updated"}

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

# ✅ ดึงข้อมูลสินค้าคงเหลือทั้งหมด
@router.get("/products/inventory", response_class=JSONResponse)
def get_products_inventory(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 3))
):
    """
    ดึงข้อมูลสินค้าคงเหลือทั้งหมดสำหรับพนักงานจัดเตรียม
    """
    products = db.query(Product).all()
    
    products_inventory = []
    for product in products:
        category = get_product_category(product.product_id)
        products_inventory.append({
            "product_id": product.product_id,
            "name": product.name,
            "price": product.price,
            "stock": product.stock,
            "category": category,
            "image_path": product.image_path  # เพิ่ม path รูปภาพสินค้า
        })
    
    return products_inventory

# ✅ เพิ่มสินค้าเข้าคลัง
@router.post("/products/add-stock", response_class=JSONResponse)
def add_product_stock(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 3))
):
    """
    เพิ่มจำนวนสินค้าในคลัง
    """
    product_id = data.get("product_id")
    quantity = data.get("quantity")
    
    if not product_id or not quantity or quantity < 1:
        raise HTTPException(status_code=400, detail="❌ ข้อมูลไม่ถูกต้อง กรุณาระบุ ID สินค้าและจำนวนที่ต้องการเพิ่ม")
    
    # ค้นหาสินค้า
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="❌ ไม่พบสินค้าที่ระบุ")
    
    # เพิ่มจำนวนสินค้า
    product.stock += quantity
    db.commit()
    
    return {"message": f"✅ เพิ่มสินค้า {product.name} จำนวน {quantity} ชิ้น เรียบร้อยแล้ว", "current_stock": product.stock}

@router.websocket("/notifications")
async def preparation_notifications(websocket: WebSocket):
    """
    ✅ WebSocket สำหรับแจ้งเตือนพนักงานจัดเตรียมเมื่อมีออเดอร์ใหม่หรือมีการเปลี่ยนแปลงในออเดอร์
    """
    await websocket.accept()
    preparation_connections.append(websocket)

    try:
        while True:
            await websocket.receive_text()  # ✅ รอข้อความจาก Client (แต่อาจไม่ต้องใช้)
    except WebSocketDisconnect:
        preparation_connections.remove(websocket)  # ✅ ลบ Connection ถ้าพนักงานหลุดออกจาก WebSocket