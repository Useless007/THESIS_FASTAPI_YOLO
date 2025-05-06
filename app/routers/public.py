# app/routers/public.py

import json

from fastapi import APIRouter, Request, Depends,HTTPException, File, UploadFile, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict, Union
from datetime import datetime

from sqlalchemy.orm import Session

import os
from app.database import get_db
from app.services.auth import get_current_user, get_current_user_or_customer
from app.models.order import Order
from app.models.user import User
from app.models.customer import Customer
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
    current_user: Optional[Union[User, Customer]] = Depends(get_current_user_or_customer)
):
    """
    แสดงหน้าแรก พร้อมสินค้าทั้งหมดและหมวดหมู่
    สนับสนุนทั้งลูกค้าและพนักงาน
    """
    # ดึงสินค้าทั้งหมดจากฐานข้อมูล
    products = db.query(Product).all()
    
    # สร้าง list ใหม่สำหรับสินค้าที่มี category
    products_with_category = []
    for product in products:
        category = get_product_category(product.product_id)
        product_dict = {
            "product_id": product.product_id,
            "name": product.name,
            "price": product.price,
            "description": product.description,
            "image_path": product.image_path,
            "category": category,
            "stock": product.stock  # เพิ่มข้อมูล stock
        }
        products_with_category.append(product_dict)
    
    return templates.TemplateResponse(
        "home.html", 
        {
            "request": request,
            "current_user": current_user,
            "products": products_with_category,
            "categories": CATEGORIES,
            "current_category": "all"
        }
    )

@router.get("/category/{category}", response_class=HTMLResponse)
def get_products_by_category(
    request: Request,
    category: str,
    db: Session = Depends(get_db),
    current_user: Optional[Union[User, Customer]] = Depends(get_current_user_or_customer)
):
    """
    แสดงสินค้าตามประเภทที่เลือก
    สนับสนุนทั้งลูกค้าและพนักงาน
    """
    # ตรวจสอบว่าประเภทที่ส่งมาถูกต้องหรือไม่
    if category not in CATEGORIES and category != "all":
        category = "all"
    
    # ดึงสินค้าทั้งหมด
    products = db.query(Product).all()
    
    # แปลงสินค้าเป็น dictionary และกรองตามประเภท
    filtered_products = []
    for product in products:
        product_category = get_product_category(product.product_id)
        product_dict = {
            "product_id": product.product_id,
            "name": product.name,
            "price": product.price,
            "description": product.description,
            "image_path": product.image_path,
            "category": product_category,
            "stock": product.stock  # เพิ่มข้อมูล stock
        }
        
        if category == "all" or product_category == category:
            filtered_products.append(product_dict)
    
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
    current_user: Optional[Union[User, Customer]] = Depends(get_current_user_or_customer)
):
    """
    แสดงหน้าตะกร้าสินค้า (รองรับทั้งลูกค้าและพนักงาน)
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
    house_number: str = Form(...),
    village_no: str = Form(...),
    subdistrict: str = Form(...),
    district: str = Form(...),
    province: str = Form(...),
    postal_code: str = Form(...),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    สั่งซื้อสินค้า พร้อมแนบสลิปการโอนเงิน และบันทึกในฐานข้อมูล
    รองรับทั้งลูกค้าและพนักงาน
    """
    from app.services.auth import get_current_actor
    from app.models.customer import Customer
    from app.models.account import Account
    
    # ดึงข้อมูลผู้ใช้ปัจจุบัน (ลูกค้าหรือพนักงาน)
    current_actor = get_current_actor(request, db)
    
    if not current_actor:
        raise HTTPException(status_code=401, detail="❌ คุณต้องล็อกอินก่อนทำการสั่งซื้อ")
    
    # ตรวจสอบว่าเป็น Customer หรือ User
    is_customer = isinstance(current_actor, Customer)

    # ดึงหรือสร้างข้อมูลลูกค้า (ถ้าเป็นพนักงานที่สั่งซื้อ)
    customer_id = None
    if is_customer:
        # ถ้าเป็นลูกค้าอยู่แล้ว ใช้ ID ของลูกค้านั้น
        customer_id = current_actor.id
        # อัปเดตข้อมูลลูกค้าผ่านฐานข้อมูล
        customer = db.query(Customer).filter(Customer.id == current_actor.id).first()
        if customer:
            # Update the associated account instead of setting read-only properties directly
            if customer.account:
                customer.account.name = fullname
                customer.account.phone = phone
    else:
        # ถ้าเป็นพนักงาน ให้ดึงข้อมูลหรือสร้างลูกค้าใหม่ที่เชื่อมโยงกับบัญชีเดียวกัน
        
        # ดึงข้อมูล Account ของพนักงาน
        from app.models.account import Account
        account = db.query(Account).filter(Account.email == current_actor.email).first()
        
        if not account:
            raise HTTPException(status_code=500, detail="❌ ไม่พบข้อมูลบัญชีของพนักงาน")
        
        # ตรวจสอบว่ามีลูกค้าที่เชื่อมโยงกับบัญชีนี้หรือไม่
        customer = db.query(Customer).filter(Customer.account_id == account.id).first()
        
        if not customer:
            # สร้างลูกค้าใหม่ที่เชื่อมโยงกับบัญชีพนักงานที่มีอยู่แล้ว
            try:
                # สร้าง customer ใหม่โดยใช้เฉพาะ account_id ซึ่งเป็น attribute ที่สามารถตั้งค่าได้
                new_customer = Customer(
                    account_id=account.id
                )
                db.add(new_customer)
                db.flush()  # ให้ได้ ID ของลูกค้าใหม่
                customer_id = new_customer.id
                customer = new_customer
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"❌ ไม่สามารถสร้างข้อมูลลูกค้าจากบัญชีพนักงานได้: {str(e)}")
        else:
            customer_id = customer.id
        
        # อัปเดตข้อมูลบัญชี
        account.name = fullname
        account.phone = phone

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

    # อัพเดทข้อมูลที่อยู่ตามประเภทของผู้ใช้
    from app.models.address import Address
    
    # สร้างหรืออัพเดทที่อยู่ของลูกค้า
    address = db.query(Address).filter(Address.customer_id == customer_id).first()
    if not address:
        address = Address(customer_id=customer_id)
        db.add(address)
    
    # อัพเดทข้อมูลที่อยู่
    address.house_number = house_number
    address.village_no = village_no
    address.subdistrict = subdistrict
    address.district = district
    address.province = province
    address.postal_code = postal_code
    
    db.commit()

    # บันทึกไฟล์สลิปการโอนเงิน
    slip_filename = f"{current_actor.email}_{payment_slip.filename}"
    slip_path = os.path.join(UPLOAD_DIR, slip_filename)

    with open(slip_path, "wb") as buffer:
        buffer.write(await payment_slip.read())

    # สร้างรายการออเดอร์ใหม่
    new_order = Order(
        customer_id=customer_id,
        total=cart_data['cart_total'],
        status="pending",
        slip_path=slip_path,
        created_at=datetime.utcnow()
    )

    # เพิ่ม order ลงฐานข้อมูลก่อนเพื่อให้ได้ order_id
    db.add(new_order)
    db.flush()  # ใช้ flush เพื่อให้ได้ order_id โดยไม่ต้อง commit

    # สร้าง order items
    from app.models.order_item import OrderItem
    for item in cart_data['cart']:
        order_item = OrderItem(
            order_id=new_order.order_id,
            product_id=item['product_id'],
            quantity=item['quantity'],
            price_at_order=item['price'],
            total_item_price=item['total']
        )
        db.add(order_item)

    # บันทึกทั้งหมดลงฐานข้อมูล
    db.commit()
    db.refresh(new_order)

    print("🛒 **บันทึกออเดอร์ใหม่ในฐานข้อมูล**")
    print(f"📧 อีเมลผู้สั่งซื้อ: {current_actor.email}")
    print(f"💵 ราคารวมทั้งหมด: ฿{cart_data['cart_total']}")
    print(f"🖼️ สลิปการโอนเงิน: {slip_path}")

    return JSONResponse(content={
        "message": "✅ สั่งซื้อสำเร็จ!",
        "order_id": new_order.order_id,
        "user_email": current_actor.email,
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
    current_user: Optional[Union[User, Customer]] = Depends(get_current_user_or_customer)
):
    """
    แสดงหน้าคำสั่งซื้อของฉัน (รองรับทั้งลูกค้าและพนักงาน)
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