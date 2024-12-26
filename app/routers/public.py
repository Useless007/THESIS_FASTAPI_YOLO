# app/routers/public.py

from fastapi import APIRouter, Request, Depends,HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional,Dict
from app.services.auth import get_current_user
from app.schemas.user import UserOut

# เพิ่ม Jinja2 Templates
templates = Jinja2Templates(directory="app/templates")

router = APIRouter(tags=["HTML"])


@router.get("/", response_class=HTMLResponse)
def get_homepage(
    request: Request,
    current_user: Optional[UserOut] = Depends(get_current_user)
):
    """
    แสดงหน้าแรก พร้อมเช็คสถานะผู้ใช้
    """
    # print(f"🏠 Current User: {current_user}")
    return templates.TemplateResponse(
        "home.html", 
        {"request": request, "current_user": current_user}
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

@router.post("/checkout", response_class=HTMLResponse)
async def print_debug(cart: Dict):
    """
    พิมพ์ข้อมูลตะกร้าสินค้าที่ลูกค้าสั่งซื้อ
    """
    if not cart.get('cart') or cart.get('cart_total') == 0:
        raise HTTPException(status_code=400, detail="❌ ตะกร้าสินค้าว่างเปล่า")

    print("🛒 **ข้อมูลตะกร้าสินค้าจากลูกค้า:**")
    for item in cart.get('cart', []):
        print(f"- สินค้า: {item['name']} | จำนวน: {item['quantity']} | รวม: ฿{item['total']}")

    print(f"💵 ราคารวมทั้งหมด: ฿{cart.get('cart_total')}")

    return JSONResponse(content={
        "message": "✅ สั่งซื้อสำเร็จ!",
        "order_id": "ORD12345",
        "cart_total": cart.get('cart_total')
    })


@router.get("/logout", response_class=RedirectResponse)
def logout():
    """
    ออกจากระบบและล้าง Token ใน Cookie
    """
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("Authorization")
    return response
