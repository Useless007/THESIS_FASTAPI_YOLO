# app/routers/product.py

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.product import ProductCreate, ProductUpdate, ProductOut
from app.schemas.order import OrderOut
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.services.auth import get_current_user

order_router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
)

@order_router.get("/my-orders", response_model=list[OrderOut])
def get_my_orders(request: Request, db: Session = Depends(get_db)):
    """
    ✅ ดึงคำสั่งซื้อของผู้ใช้ที่ล็อกอินอยู่ (รองรับทั้งลูกค้าและพนักงาน)
    """
    from app.services.auth import get_current_actor
    from app.models.customer import Customer
    
    # ดึงข้อมูลผู้ใช้ปัจจุบัน (ทั้งลูกค้าและพนักงาน)
    current_actor = get_current_actor(request, db)
    
    if not current_actor:
        print("❌ Unauthorized access - No current_user")
        return JSONResponse(content={"message": "❌ Unauthorized"}, status_code=401)
    
    # ตรวจสอบว่าเป็น Customer หรือ User
    is_customer = isinstance(current_actor, Customer)
    
    print(f"🔍 Fetching orders for {'customer' if is_customer else 'user'}: {current_actor.email}")
    
    if is_customer:
        # ดึงคำสั่งซื้อของลูกค้า
        orders = db.query(Order).filter(Order.customer_id == current_actor.id).all()
    else:
        # ถ้าเป็นพนักงาน ให้ดึงคำสั่งซื้อจากลูกค้าที่มีอีเมลเดียวกัน
        customer = db.query(Customer).filter(Customer.email == current_actor.email).first()
        if customer:
            orders = db.query(Order).filter(Order.customer_id == customer.id).all()
        else:
            # ถ้าไม่มีข้อมูลลูกค้าที่ตรงกัน ให้ส่ง array ว่าง
            print("❌ ไม่พบข้อมูลลูกค้าที่ตรงกับพนักงาน")
            return JSONResponse(content=[], status_code=200)

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

@order_router.get("/{order_id}/items")
def get_order_items(order_id: int, request: Request, db: Session = Depends(get_db)):
    """
    ✅ ดึงรายการสินค้าในคำสั่งซื้อ (รองรับทั้งลูกค้าและพนักงาน)
    """
    from app.services.auth import get_current_actor
    from app.models.customer import Customer
    
    # ดึงข้อมูลผู้ใช้ปัจจุบัน (ทั้งลูกค้าและพนักงาน)
    current_actor = get_current_actor(request, db)
    
    if not current_actor:
        print("❌ Unauthorized access - No current_user")
        return JSONResponse(content={"message": "❌ Unauthorized"}, status_code=401)
    
    # ตรวจสอบว่าเป็น Customer หรือ User
    is_customer = isinstance(current_actor, Customer)
    
    # ตรวจสอบว่าคำสั่งซื้อเป็นของผู้ใช้นี้จริงหรือไม่
    if is_customer:
        # ถ้าเป็นลูกค้า ตรวจสอบด้วย customer_id
        order = db.query(Order).filter(Order.order_id == order_id, Order.customer_id == current_actor.id).first()
    else:
        # ถ้าเป็นพนักงาน ตรวจสอบว่ามีข้อมูลลูกค้าที่ตรงกันหรือไม่
        customer = db.query(Customer).filter(Customer.email == current_actor.email).first()
        if customer:
            order = db.query(Order).filter(Order.order_id == order_id, Order.customer_id == customer.id).first()
        else:
            order = None
    
    if not order:
        print(f"❌ Order {order_id} not found or not authorized")
        raise HTTPException(status_code=404, detail="Order not found or unauthorized")

    # ดึงรายการสินค้าในคำสั่งซื้อ
    order_items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    
    # เตรียมข้อมูลสำหรับส่งกลับ
    items_detail = []
    for item in order_items:
        product = db.query(Product).filter(Product.product_id == item.product_id).first()
        
        items_detail.append({
            "item_id": item.item_id,
            "product_id": item.product_id,
            "product_name": product.name if product else "Unknown Product",
            "quantity": item.quantity,
            "price_at_order": item.price_at_order,
            "total_item_price": item.total_item_price
        })
    
    return JSONResponse(content=items_detail, status_code=200)