# app/routers/admin.py

import json
from fastapi import APIRouter, Depends, Request, HTTPException, WebSocket, WebSocketDisconnect, Query
from typing import List
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from app.services.ws_manager import NotifyPayload, notify_admin
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, cast, Date, and_, or_
from app.models.user import User
from app.models.order import Order
from app.models.camera import Camera
from app.services.auth import get_user_with_role_and_position_and_isActive, get_current_user, get_user_with_role
from app.services.ws_manager import admin_connections
from app.database import get_db
from fastapi.templating import Jinja2Templates
from app.crud import camera as camera_crud
from app.schemas.camera import CameraCreate, CameraUpdate, Camera as CameraSchema
from app.crud import user as user_crud
from app.crud import dashboard_crud

admin_connections: List[WebSocket] = []
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

    if current_user.role_id == 1 and current_user.position_id == 2:
        print(f"🛡️ Admin Dashboard Access by: {current_user.email}")
        return templates.TemplateResponse("admin_dashboard.html", {"request": request, "current_user": current_user})
    elif current_user.role_id == 1 and current_user.position_id == 4:
        print(f"🛡️ Packing Dashboard Access by: {current_user.email}")
        return templates.TemplateResponse("packing_dashboard.html", {"request": request, "current_user": current_user})
    elif current_user.role_id == 1 and current_user.position_id == 3:    
        print(f"🛡️ Preparation Dashboard Access by: {current_user.email}")
        return templates.TemplateResponse("preparation_dashboard.html", {"request": request, "current_user": current_user})
    elif current_user.role_id == 1 and current_user.position_id == 1:
        print(f"🛡️ Executive Dashboard Access by: {current_user.email}")
        return templates.TemplateResponse("executive_dashboard.html", {"request": request, "current_user": current_user})
    else:
        raise HTTPException(status_code=403, detail="❌ Access Denied: Role or Position Invalid")

# Route สำหรับดึงข้อมูลแดชบอร์ด
@router.get("/dashboard-data")
def get_dashboard_data(
    db: Session = Depends(get_db),
    current_user=Depends(get_user_with_role_and_position_and_isActive(1, 2))
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
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    print(f"🛡️ Activate Management Access by: {current_user.email}")
    return templates.TemplateResponse("admin_activate.html", {"request": request, "current_user": current_user})

# Route สำหรับแสดงหน้าจัดการออเดอร์
@router.get("/orders", response_class=HTMLResponse)
def get_order_management(
    request: Request,
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    print(f"🛡️ Order Management Access by: {current_user.email}")
    return templates.TemplateResponse("admin_orders.html", {"request": request, "current_user": current_user})

@router.get("/users", response_class=JSONResponse)
def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """
    ✅ ดึงข้อมูลผู้ใช้ที่เป็น employee เท่านั้นสำหรับจัดการบทบาทและตำแหน่ง
    """
    users = db.query(User).filter(User.role_id == 1).all()  # ดึงเฉพาะ employee
    user_data = [{"id": user.id, "name": user.name, "role": user.role, "position": user.position} for user in users]
    return user_data
    
@router.put("/users/{user_id}/update-role", response_class=JSONResponse)
def update_user_role(
    user_id: int,
    role_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """
    ✅ อัปเดตบทบาทของผู้ใช้
    """
    new_role_id = role_data.get("role")
    if not new_role_id or new_role_id not in ["1", "2"]:  # 1=employee, 2=customer
        raise HTTPException(status_code=400, detail="❌ Invalid role specified")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="❌ User not found")
    
    user.role_id = int(new_role_id)  # แปลงเป็น int ก่อนบันทึก
    
    # ถ้าเปลี่ยนเป็น customer ให้ลบ position_id
    if new_role_id == 2:
        user.position_id = None
    
    db.commit()
    db.refresh(user)
    
    role_name = "employee" if new_role_id == 1 else "customer"
    return {"message": f"✅ บทบาทของผู้ใช้ {user_id} ถูกอัปเดตเป็น {role_name}"}

@router.put("/users/{user_id}/update-position", response_class=JSONResponse)
def update_user_position(
    user_id: int,
    position_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """
    ✅ อัปเดตตำแหน่ง (Position) ของผู้ใช้
    """
    new_position_id = position_data.get("position")
    valid_positions = ["1", "2", "3", "4"]  # 1=executive, 2=admin, 3=preparation, 4=packing

    if not new_position_id or new_position_id not in valid_positions:
        raise HTTPException(status_code=400, detail="❌ Invalid position specified")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="❌ User not found")
    
    # ตรวจสอบว่าเป็น employee เท่านั้นที่มี position
    if user.role_id != 1:
        raise HTTPException(status_code=400, detail="❌ Only employees can have positions")

    user.position_id = int(new_position_id)  # แปลงเป็น int ก่อนบันทึก
    db.commit()
    db.refresh(user)

    position_names = {
        1: "executive",
        2: "admin",
        3: "preparation staff",
        4: "packing staff"
    }
    position_name = position_names.get(new_position_id, "unknown")
    
    return {"message": f"✅ ตำแหน่งของผู้ใช้ {user_id} ถูกอัปเดตเป็น {position_name}"}

@router.delete("/users/{user_id}", response_class=JSONResponse)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """
    ✅ ลบผู้ใช้จากระบบ
    """
    # ป้องกันไม่ให้ลบตัวเอง
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="❌ Cannot delete yourself")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="❌ User not found")

    # ป้องกันไม่ให้ลบ admin หรือ executive คนสุดท้าย
    if user.role_id == 1 and user.position_id in [1, 2]:
        admin_count = db.query(User).filter(
            User.role_id == 1, 
            User.position_id.in_([1, 2]),
            User.id != user_id
        ).count()
        
        if admin_count == 0:
            raise HTTPException(status_code=400, detail="❌ Cannot delete the last admin/executive")

    db.delete(user)
    db.commit()
    
    return {"message": f"✅ ผู้ใช้ {user_id} ถูกลบสำเร็จ"}


# Route สำหรับแสดงหน้าจัดการroles
@router.get("/roles", response_class=HTMLResponse)
def get_order_management(
    request: Request,
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    print(f"🛡️ Order Management Access by: {current_user.email}")
    return templates.TemplateResponse("admin_roles.html", {"request": request, "current_user": current_user})

# Route สำหรับแสดงหน้าจัดการ
@router.get("/working-status", response_class=HTMLResponse)
def get_working_logs(
    request: Request,
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    print(f"🛡️ Order Management Access by: {current_user.email}")
    return templates.TemplateResponse("admin_logs.html", {"request": request, "current_user": current_user})


@router.get("/pending_order", response_class=JSONResponse)
def get_pending_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """
    ดึงข้อมูลออเดอร์ที่มีสถานะ pending
    """
    pending_orders = db.query(Order).filter(Order.status == "pending").all()
    
    orders_data = []
    for order in pending_orders:
        # ดึงข้อมูลสินค้าจาก relationship แทน
        items_data = []
        if order.order_items:
            for item in order.order_items:
                items_data.append({
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "price": item.price_at_order,
                    "total": item.total_item_price,
                    "product_name": item.product.name if item.product else "Unknown"
                })

        # ตรวจสอบ slip_path
        if order.slip_path:
            normalized_slip_path = order.slip_path.replace("\\", "/")  # แก้ไข backslash เป็น slash
            slip_path = f"/{normalized_slip_path}" if not normalized_slip_path.startswith("/") else normalized_slip_path
        else:
            slip_path = None

        orders_data.append({
            "id": order.order_id,
            "email": order.customer.email if order.customer else None,  # แก้จาก order.user เป็น order.customer
            "item": items_data,
            "total": order.total,
            "status": order.status,
            "created_at": order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "slip_path": slip_path  # URL ถูกต้อง
        })

    return {"orders": orders_data}

@router.websocket("/notifications")
async def admin_notifications(websocket: WebSocket):
    """
    ✅ WebSocket สำหรับแจ้งเตือนแอดมินเมื่อออเดอร์ถูกเปลี่ยนเป็น `pending`
    """
    await websocket.accept()
    admin_connections.append(websocket)

    try:
        while True:
            await websocket.receive_text()  # ✅ รอข้อความจาก Client (แต่อาจไม่ต้องใช้)
    except WebSocketDisconnect:
        admin_connections.remove(websocket)  # ✅ ลบ Connection ถ้าแอดมินหลุดออกจาก WebSocket


@router.post("/trigger-notify")
async def trigger_notify(payload: NotifyPayload, request: Request):
    """
    ✅ Endpoint ให้ Thesis-API เรียกเพื่อให้ Home แจ้งเตือน Admin ผ่าน WebSocket
    """
    message = {
        "order_id": payload.order_id,
        "message": f"⚠️ ออเดอร์ #{payload.order_id} เป็น PENDING - {payload.reason}",
    }

    # ตรวจสอบว่ามี Admin Online หรือไม่
    if not admin_connections:
        return {"status": "no_admin_online"}

    # ส่งข้อความแจ้งเตือนไปให้ Admin ทุกคนที่เชื่อม WebSocket อยู่
    for conn in admin_connections:
        await conn.send_json(message)

    return {"status": "notified", "sent_to": len(admin_connections)}


# Route สำหรับอนุมัติออเดอร์
@router.put("/orders/{order_id}/approve", response_class=JSONResponse)
def approve_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
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
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """
    เปลี่ยนบทบาท (Role) ของผู้ใช้
    """
    valid_roles = ["2", "4", "3"]  # 2 = Employee, 4 = Packing Staff, 3 = Preparation Staff

    if role not in valid_roles:
        raise HTTPException(status_code=400, detail="❌ Invalid role specified")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="❌ User not found")

    user.role_id = 1  # เปลี่ยนบทบาทเป็น Employee
    user.position_id = role
    user.is_active = False
    db.commit()
    return {"message": f"✅ User {user_id} role updated to {role}"}

# Route สำหรับยกเลิกออเดอร์
@router.delete("/orders/{order_id}/cancel", response_class=JSONResponse)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
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
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """
    ดึงข้อมูลพนักงานที่ยังไม่ได้รับการอนุมัติ (is_active = False)
    """
    from app.models.account import Account
    
    # ใช้ join กับตาราง Account เพื่อตรวจสอบ is_active
    users = db.query(User)\
             .join(Account, User.account_id == Account.id)\
             .filter(Account.is_active == False, User.role_id == 1)\
             .all()
    
    print(f"🔍 Found {len(users)} employees waiting for activation")
    
    # แปลงข้อมูลเพื่อส่งกลับในรูปแบบ JSON
    user_data = []
    for user in users:
        user_data.append({
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "position": user.position.position_name if user.position else None
        })
    
    return user_data

@router.get("/customers-to-activate", response_class=JSONResponse)
def get_customers_to_activate(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """
    ดึงข้อมูลผู้ใช้ที่เป็น Customer และยังไม่ Active
    """
    customers = db.query(User).filter(User.is_active == False, User.role_id == 2).all()
    
    customer_data = [
        {
            "id": customer.id,
            # เปลี่ยนจาก customer.name เป็น customer.email
            "name": customer.email,
            "email": customer.email,
            "role_id": customer.role_id,
        }
        for customer in customers
    ]
    return {"customers": customer_data}

@router.get("/work-status", response_class=JSONResponse)
def get_work_status(
    date: str,  # รับวันที่ที่ต้องการดูข้อมูล เช่น "2024-02-01"
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """
    ✅ ดึงสถานะการทำงานของพนักงานแต่ละวัน
    """
    from sqlalchemy.orm import joinedload
    
    orders = db.query(Order)\
        .options(
            joinedload(Order.customer),  # ใช้ customer แทน user
            joinedload(Order.assigned_user),
            joinedload(Order.camera)
        )\
        .filter(and_(
            Order.created_at >= f"{date} 00:00:00",
            Order.created_at <= f"{date} 23:59:59"
        )).all()

    order_data = []
    for order in orders:
        print(order)
        # เอาชื่อกล้องแทนหมายเลขโต๊ะ
        camera_name = "N/A"
        if order.camera:
            camera_name = order.camera.name
        
        # เอาชื่อพนักงานที่ได้รับมอบหมาย
        employee_name = "N/A"
        if order.assigned_user:
            employee_name = order.assigned_user.name or order.assigned_user.email
        
        # เอาชื่อลูกค้าที่สั่ง
        customer_name = "N/A"  
        if order.customer:  # ใช้ customer แทน user
            customer_name = order.customer.email
        
        order_data.append({
            "order_id": order.order_id,
            "camera_name": camera_name,
            "employee_name": employee_name,
            "customer_email": customer_name,
            "status": order.status,
            "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return {"work_status": order_data}

@router.get("/my-work-status", response_class=JSONResponse)
def get_my_work_status(
    date: str,  # รับวันที่ที่ต้องการดูข้อมูล เช่น "2024-02-01"
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    ✅ ดึงประวัติการทำงานของพนักงานตามวันที่
    """
    try:
        # แปลง date string เป็น datetime
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        
        # กำหนดช่วงเวลาเริ่มต้นและสิ้นสุดของวัน
        start_date = date_obj.replace(hour=0, minute=0, second=0)
        end_date = date_obj.replace(hour=23, minute=59, second=59)

        # หาหมายเลขโต๊ะที่พนักงานใช้งาน
        table_info = "N/A"
        camera = db.query(Camera).filter(Camera.assigned_to == current_user.id).first()
        if camera:
            table_info = camera.name

        # ดึงคำสั่งซื้อทั้งหมดที่พนักงานได้รับมอบหมาย
        orders = (
            db.query(Order)
            .options(
                joinedload(Order.order_items),
                joinedload(Order.user)  # โหลดข้อมูลลูกค้าด้วย
            )
            .filter(
                Order.assigned_to == current_user.id,
                Order.created_at >= start_date,
                Order.created_at <= end_date
            )
            .order_by(Order.created_at.desc())
            .all()
        )

        order_data = []
        for order in orders:
            # นับจำนวนสินค้า
            item_count = len(order.order_items) if order.order_items else 0
            
            # ดึง email ของลูกค้า
            customer_email = order.user.email if order.user else "N/A"

            order_data.append({
                "order_id": order.order_id,
                "camera_name": table_info,  # ใช้ชื่อกล้องแทน table_number
                "customer_email": customer_email,
                "status": order.status,
                "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "total": float(order.total),
                "item_count": item_count,
                "is_verified": order.is_verified
            })

        # คำนวณสถิติ
        completed_orders = sum(1 for order in order_data if order["status"] == "completed")
        total_sales = sum(order["total"] for order in order_data if order["status"] == "completed")

        return {
            "my_work_status": order_data,
            "statistics": {
                "total_orders": len(order_data),
                "completed_orders": completed_orders,
                "completion_rate": f"{(completed_orders/len(order_data)*100):.1f}%" if order_data else "0%",
                "total_sales": total_sales
            },
            "date": date
        }

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"รูปแบบวันที่ไม่ถูกต้อง กรุณาใช้รูปแบบ YYYY-MM-DD: {str(ve)}")
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Error in get_my_work_status: {error_detail}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {str(e)}")

# Route สำหรับแสดงหน้าประวัติการทำงาน
@router.get("/my-work-history", response_class=HTMLResponse)
def get_my_work_history(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    ✅ แสดงหน้าประวัติการทำงานของพนักงาน
    """
    return templates.TemplateResponse("my_work_history.html", {"request": request, "current_user": current_user})

# หน้า Executive Dashboard
@router.get("/executive", response_class=HTMLResponse)
async def get_executive_dashboard(
    request: Request,
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 1))
):
    return templates.TemplateResponse(
        "executive_dashboard.html",
        {"request": request, "current_user": current_user}
    )



# API สำหรับดึงข้อมูล Dashboard
@router.get("/api/executive/dashboard-data")
async def get_executive_dashboard_data(
    period: str = Query('today', enum=['today', 'week', 'month', 'year']),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 1))
):
    return dashboard_crud.get_executive_dashboard_data(db, period)


# Camera Management Routes
@router.get("/cameras", response_class=HTMLResponse)
async def get_cameras_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """หน้าจัดการกล้อง"""
    cameras = camera_crud.get_cameras(db)
    
    # แก้ไขส่วนนี้ให้ดึงพนักงานโดยใช้ role_id แทน role string
    employees = db.query(User).filter(User.role_id == 1,User.position_id == 4).all()  # 1 = employee
    
    return templates.TemplateResponse(
        "cameras.html",
        {
            "request": request,
            "cameras": cameras,
            "employees": employees
        }
    )

# Camera API Endpoints
@router.get("/api/cameras", response_model=List[CameraSchema])
async def get_cameras(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """ดึงข้อมูลกล้องทั้งหมด"""
    return camera_crud.get_cameras(db)

@router.post("/api/cameras", response_model=CameraSchema)
async def create_camera(
    camera: CameraCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """สร้างกล้องใหม่"""
    db_camera = camera_crud.create_camera(db, camera)
    return db_camera

@router.put("/api/cameras/{camera_id}", response_model=CameraSchema)
async def update_camera(
    camera_id: int,
    camera: CameraUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """อัปเดตข้อมูลกล้อง"""
    db_camera = camera_crud.update_camera(db, camera_id, camera)
    if not db_camera:
        raise HTTPException(status_code=404, detail="ไม่พบกล้องที่ต้องการหรือหมายเลขโต๊ะซ้ำ")
    return db_camera

@router.delete("/api/cameras/{camera_id}")
async def delete_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """ลบกล้อง"""
    if not camera_crud.delete_camera(db, camera_id):
        raise HTTPException(status_code=404, detail="ไม่พบกล้องที่ต้องการ")
    return {"status": "success", "message": "ลบกล้องเรียบร้อยแล้ว"}

# สร้าง Router สำหรับจัดการข้อมูลลูกค้าจากฝั่งแอดมิน
@router.get("/customers", response_class=JSONResponse)
def get_all_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """
    ✅ ดึงข้อมูลลูกค้าทั้งหมดสำหรับแสดงในหน้า admin
    """
    from app.models.customer import Customer
    from app.models.address import Address
    
    # ดึงข้อมูลลูกค้าทั้งหมดพร้อม relationship
    customers = db.query(Customer).all()
    customer_list = []
    
    for customer in customers:
        customer_data = {
            "id": customer.id,
            "email": customer.email,
            "name": customer.name,
            "phone": customer.phone,
            "created_at": customer.created_at,
            "is_active": customer.is_active,
            "addresses": []
        }
        
        # ดึงข้อมูลที่อยู่ของลูกค้า
        for address in customer.addresses:
            address_data = {
                "id": address.id,
                "house_number": address.house_number,
                "village_no": address.village_no,
                "subdistrict": address.subdistrict,
                "district": address.district,
                "province": address.province,
                "postal_code": address.postal_code
            }
            customer_data["addresses"].append(address_data)
            
        customer_list.append(customer_data)
    
    return customer_list

@router.put("/customers/{customer_id}/activate", response_class=JSONResponse)
def activate_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """
    ✅ เปิดใช้งานบัญชีลูกค้า
    """
    from app.crud.customer import update_customer_status, get_customer_by_id
    
    db_customer = get_customer_by_id(db=db, customer_id=customer_id)
    if not db_customer:
        raise HTTPException(status_code=404, detail="❌ ไม่พบข้อมูลลูกค้า")
    
    result = update_customer_status(db=db, customer_id=customer_id, is_active=True)
    return {"message": f"✅ เปิดใช้งานบัญชีลูกค้า {result.email} สำเร็จ"}

@router.put("/customers/{customer_id}/deactivate", response_class=JSONResponse)
def deactivate_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """
    ✅ ปิดใช้งานบัญชีลูกค้า
    """
    from app.crud.customer import update_customer_status, get_customer_by_id
    
    db_customer = get_customer_by_id(db=db, customer_id=customer_id)
    if not db_customer:
        raise HTTPException(status_code=404, detail="❌ ไม่พบข้อมูลลูกค้า")
    
    result = update_customer_status(db=db, customer_id=customer_id, is_active=False)
    return {"message": f"✅ ปิดใช้งานบัญชีลูกค้า {result.email} สำเร็จ"}

@router.delete("/customers/{customer_id}", response_class=JSONResponse)
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """
    ✅ ลบบัญชีลูกค้า
    """
    from app.crud.customer import delete_customer, get_customer_by_id
    
    db_customer = get_customer_by_id(db=db, customer_id=customer_id)
    if not db_customer:
        raise HTTPException(status_code=404, detail="❌ ไม่พบข้อมูลลูกค้า")
    
    email = db_customer.email
    delete_customer(db=db, customer_id=customer_id)
    return {"message": f"✅ ลบบัญชีลูกค้า {email} สำเร็จ"}

# Route สำหรับแสดงหน้าจัดการลูกค้า
@router.get("/customer-management", response_class=HTMLResponse)
def get_customer_management(
    request: Request,
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
):
    """
    แสดงหน้าจัดการลูกค้า (สำหรับแอดมิน)
    """
    print(f"🛡️ Customer Management Access by: {current_user.email}")
    return templates.TemplateResponse("admin_customers.html", {"request": request, "current_user": current_user})
