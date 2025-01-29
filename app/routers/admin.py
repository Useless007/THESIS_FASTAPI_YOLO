# app/routers/admin.py

import json
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from app.models.user import User
from app.models.order import Order
from app.services.auth import get_user_with_role_and_position_and_isActive, get_current_user
from app.database import get_db
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(prefix="/admin", tags=["Admin"])

# Route สำหรับแสดงหน้า Admin Dashboard
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_redirect(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    ตรวจสอบบทบาทของผู้ใช้และเปลี่ยนเส้นทางไปยังแดชบอร์ดที่เหมาะสม
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="❌ Unauthorized")

    if current_user.role == "employee" and current_user.position == "admin":
        print(f"🛡️ Admin Dashboard Access by: {current_user.email}")
        return templates.TemplateResponse("admin_dashboard.html", {"request": request, "current_user": current_user})
    elif current_user.role == "employee" and current_user.position == "packing staff":
        print(f"🛡️ Packing Dashboard Access by: {current_user.email}")
        return templates.TemplateResponse("packing_dashboard.html", {"request": request, "current_user": current_user})
    elif current_user.role == "employee" and current_user.position == "preparation staff":    
        print(f"🛡️ Preparation Dashboard Access by: {current_user.email}")
        return templates.TemplateResponse("preparation_dashboard.html", {"request": request, "current_user": current_user})
    else:
        raise HTTPException(status_code=403, detail="❌ Access Denied: Role or Position Invalid")



# Route สำหรับดึงข้อมูลแดชบอร์ด
@router.get("/dashboard-data")
def get_dashboard_data(
    db: Session = Depends(get_db),
    current_user=Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    """
    ดึงข้อมูลแดชบอร์ด พร้อมยอดขายวันนี้จากออเดอร์ที่สถานะเป็น completed
    """
    # นับจำนวนผู้ใช้ทั้งหมด
    user_count = db.query(User).count()

    # คำนวณยอดขายวันนี้ จากตาราง Order
    sales_today = (
        db.query(func.sum(Order.total))
        .filter(
            Order.status == "completed",  # เฉพาะสถานะที่เป็น completed
            cast(Order.created_at, Date) == datetime.utcnow().date()  # เฉพาะออเดอร์วันนี้
        )
        .scalar() or 0.0  # หากไม่มีข้อมูลให้ส่ง 0.0
    )

    return {
        "user_count": user_count,
        "sales_today": sales_today
    }

# Route สำหรับ Activate ผู้ใช้
@router.get("/activate", response_class=HTMLResponse)
def get_user_management(
    request: Request,
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    print(f"🛡️ Activate Management Access by: {current_user.email}")
    return templates.TemplateResponse("admin_activate.html", {"request": request, "current_user": current_user})

# Route สำหรับแสดงหน้าจัดการออเดอร์
@router.get("/orders", response_class=HTMLResponse)
def get_order_management(
    request: Request,
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    print(f"🛡️ Order Management Access by: {current_user.email}")
    return templates.TemplateResponse("admin_orders.html", {"request": request, "current_user": current_user})


@router.get("/pending_order", response_class=JSONResponse)
def get_pending_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    """
    ดึงข้อมูลออเดอร์ที่มีสถานะ pending
    """
    pending_orders = db.query(Order).filter(Order.status == "pending").all()
    
    orders_data = []
    for order in pending_orders:
        try:
            # แปลง item จาก String กลับมาเป็น JSON
            item_data = json.loads(order.item)
        except json.JSONDecodeError:
            item_data = [{"error": "❌ Invalid JSON format"}]
            print(f"❌ JSONDecodeError ใน Order ID: {order.order_id}")

        # ตรวจสอบ slip_path
        if order.slip_path:
            normalized_slip_path = order.slip_path.replace("\\", "/")  # แก้ไข backslash เป็น slash
            slip_path = f"/{normalized_slip_path}" if not normalized_slip_path.startswith("/") else normalized_slip_path
        else:
            slip_path = None

        orders_data.append({
            "id": order.order_id,
            "email": order.email,
            "item": item_data,
            "total": order.total,
            "status": order.status,
            "created_at": order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "slip_path": slip_path  # URL ถูกต้อง
        })

    return {"orders": orders_data}





# Route สำหรับอนุมัติออเดอร์
@router.put("/orders/{order_id}/approve", response_class=JSONResponse)
def approve_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    """
    อนุมัติออเดอร์ (เปลี่ยนสถานะเป็น confirmed)
    """
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="❌ Order not found")

    order.status = "confirmed"
    db.commit()
    return {"message": f"✅ Order {order_id} confirmed successfully"}

@router.put("/users/{user_id}/change-role", response_class=JSONResponse)
def change_user_role(
    user_id: int,
    role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    """
    เปลี่ยนบทบาท (Role) ของผู้ใช้
    """
    valid_roles = ["admin", "packing staff", "preparation staff"]

    if role not in valid_roles:
        raise HTTPException(status_code=400, detail="❌ Invalid role specified")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="❌ User not found")

    user.role = str("employee")
    user.position = role
    user.is_active = False
    db.commit()
    return {"message": f"✅ User {user_id} role updated to {role}"}


# Route สำหรับยกเลิกออเดอร์
@router.delete("/orders/{order_id}/cancel", response_class=JSONResponse)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    """
    ยกเลิกออเดอร์ (ลบออกจากฐานข้อมูล)
    """
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="❌ Order not found")

    db.delete(order)
    db.commit()
    return {"message": f"✅ Order {order_id} canceled successfully"}



# Route สำหรับดึงข้อมูลผู้ใช้ที่ต้องการ Activate
@router.get("/employees-to-activate", response_class=JSONResponse)
def get_users_to_activate(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    users = db.query(User).filter(User.is_active == False, User.role == "employee").all()
    return users

@router.get("/customers-to-activate", response_class=JSONResponse)
def get_customers_to_activate(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    """
    ดึงข้อมูลผู้ใช้ที่เป็น Customer และยังไม่ Active
    """
    customers = db.query(User).filter(User.is_active == False, User.role == "customer").all()
    
    customer_data = [
        {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "role": customer.role
        }
        for customer in customers
    ]
    return {"customers": customer_data}