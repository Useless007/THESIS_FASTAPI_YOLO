# app/routers/public.py

import json

from fastapi import APIRouter, Request, Depends,HTTPException, File, UploadFile, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional,Dict

from sqlalchemy.orm import Session

import os
from app.database import get_db
from app.services.auth import get_current_user
from app.models.order import Order
from app.models.user import User
from app.schemas.user import UserOut
from app.models.product import Product
from app.utils.product_categories import get_product_category, CATEGORIES

# เพิ่ม Jinja2 Templates
templates = Jinja2Templates(directory="app/templates")

# กำหนดโฟลเดอร์สำหรับเก็บสลิป
UPLOAD_DIR = "uploads/payment_slips"
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter(tags=["HTML"])


# @router.get("/", response_class=HTMLResponse)
# def get_homepage(
#     request: Request,
#     current_user: Optional[UserOut] = Depends(get_current_user)
# ):
#     """
#     แสดงหน้าแรก พร้อมเช็คสถานะผู้ใช้
#     """
#     # print(f"🏠 Current User: {current_user}")
#     return templates.TemplateResponse(
#         "home.html", 
#         {"request": request, "current_user": current_user}
#     )

@router.get("/", response_class=HTMLResponse)
def get_homepage(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[UserOut] = Depends(get_current_user)
):
    """
    แสดงหน้าแรก พร้อมสินค้าทั้งหมดและหมวดหมู่
    """
    # ดึงสินค้าทั้งหมดจากฐานข้อมูล
    products = db.query(Product).all()
    
    # เพิ่ม category ให้แต่ละสินค้า
    for product in products:
        product.category = get_product_category(product.product_id)
    
    return templates.TemplateResponse(
        "home.html", 
        {
            "request": request,
            "current_user": current_user,
            "products": products,
            "categories": CATEGORIES,
            "current_category": "all"
        }
    )

@router.get("/category/{category}", response_class=HTMLResponse)
def get_products_by_category(
    request: Request,
    category: str,
    db: Session = Depends(get_db),
    current_user: Optional[UserOut] = Depends(get_current_user)
):
    """
    แสดงสินค้าตามประเภทที่เลือก
    """
    # ตรวจสอบว่าประเภทที่ส่งมาถูกต้องหรือไม่
    if category not in CATEGORIES and category != "all":
        category = "all"
    
    # ดึงสินค้าทั้งหมด
    products = db.query(Product).all()
    
    # กรองสินค้าตามประเภท
    filtered_products = []
    if category == "all":
        filtered_products = products
    else:
        for product in products:
            product_category = get_product_category(product.product_id)
            if product_category == category:
                product.category = product_category
                filtered_products.append(product)
    
    # เพิ่ม category ให้กับสินค้าที่เหลือ
    for product in filtered_products:
        if not hasattr(product, 'category'):
            product.category = get_product_category(product.product_id)
    
    return templates.TemplateResponse(
        "home.html", 
        {
            "request": request,
            "current_user": current_user,
            "products": filtered_products,
            "categories": CATEGORIES,
            "current_category": category
        }
    )
    

@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return RedirectResponse(url="/static/favicon.ico")

@router.get("/cart", response_class=HTMLResponse)
def get_cart_page(
    request: Request,
    current_user: Optional[UserOut] = Depends(get_current_user)
):
    """
    แสดงหน้าตะกร้าสินค้า
    """
    return templates.TemplateResponse(
        "cart.html", 
        {"request": request, "current_user": current_user}
    )

@router.post("/checkout", response_class=JSONResponse)
async def checkout(
    cart: str = Form(...),  # รับ cart เป็น JSON string จาก FormData
    payment_slip: UploadFile = File(...),
    fullname: str = Form(...),
    phone: str = Form(...),
    address: str = Form(...),
    province: str = Form(...),
    postal_code: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Optional[UserOut] = Depends(get_current_user)
):
    """
    สั่งซื้อสินค้า พร้อมแนบสลิปการโอนเงิน และบันทึกในฐานข้อมูล
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="❌ คุณต้องล็อกอินก่อนทำการสั่งซื้อ")

    try:
        cart_data = json.loads(cart)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"❌ ไม่สามารถอ่านข้อมูลตะกร้าได้: {str(e)}")

    if not cart_data.get('cart') or cart_data.get('cart_total') == 0:
        raise HTTPException(status_code=400, detail="❌ ตะกร้าสินค้าว่างเปล่า")

    # ตรวจสอบไฟล์สลิปการโอนเงิน
    if payment_slip.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(status_code=400, detail="❌ อัปโหลดได้เฉพาะไฟล์ .jpg, .jpeg หรือ .png เท่านั้น")

    if payment_slip.size > 15 * 1024 * 1024:  # 15MB
        raise HTTPException(status_code=400, detail="❌ ขนาดไฟล์ต้องไม่เกิน 15MB")

    # อัพเดทที่อยู่ของผู้ใช้
    user = db.query(User).filter(User.email == current_user.email).first()
    if user:
        # สร้างที่อยู่แบบเต็ม
        full_address = f"{address}, {province} {postal_code}"
        user.name = fullname
        user.phone = phone
        user.address = full_address
        db.commit()

    # บันทึกไฟล์สลิปการโอนเงิน
    slip_filename = f"{current_user.email}_{payment_slip.filename}"
    slip_path = os.path.join(UPLOAD_DIR, slip_filename)

    with open(slip_path, "wb") as buffer:
        buffer.write(await payment_slip.read())

    # บันทึก JSON ด้วย double quotes
    cart_json = json.dumps(cart_data['cart'], ensure_ascii=False)

    # สร้างรายการออเดอร์ใหม่
    new_order = Order(
        email=current_user.email,
        item=cart_json,
        total=cart_data['cart_total'],
        status="pending",
        slip_path=slip_path
    )

    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    print("🛒 **บันทึกออเดอร์ใหม่ในฐานข้อมูล**")
    print(f"📧 อีเมลผู้สั่งซื้อ: {current_user.email}")
    print(f"💵 ราคารวมทั้งหมด: ฿{cart_data['cart_total']}")
    print(f"🖼️ สลิปการโอนเงิน: {slip_path}")

    return JSONResponse(content={
        "message": "✅ สั่งซื้อสำเร็จ!",
        "order_id": new_order.order_id,
        "user_email": current_user.email,
        "cart_total": cart_data['cart_total'],
        "slip_path": slip_path
    })

@router.get("/logout", response_class=RedirectResponse)
def logout():
    """
    ✅ ออกจากระบบและล้าง Token ใน Cookie
    """
    response = RedirectResponse(url="/login", status_code=303)

    # ✅ ลบ Cookie โดยต้องระบุ `domain` และ `path` ให้ตรงกัน
    response.delete_cookie(
        key="Authorization",
        path="/", 
        # domain=".jintaphas.tech"  # ✅ ต้องตรงกับตอนเซ็ต Cookie
    )

    return response



@router.get("/my-orders", response_class=HTMLResponse)
def get_my_orders_page(
    request: Request,
    current_user: Optional[UserOut] = Depends(get_current_user)
):
    """
    แสดงหน้าคำสั่งซื้อของฉัน
    """
    return templates.TemplateResponse(
        "my_orders.html",
        {"request": request, "current_user": current_user}
    )

@router.get("/contact", response_class=HTMLResponse)
def get_contact_page(
    request: Request
):
    """
    แสดงหน้าติดต่อเรา
    """
    return templates.TemplateResponse(
        "contact.html", 
        {"request": request}
    )