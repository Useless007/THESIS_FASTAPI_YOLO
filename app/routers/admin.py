# app/routers/admin.py

import json
from fastapi import APIRouter, Depends, Request, HTTPException, WebSocket, WebSocketDisconnect
from typing import List
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from app.services.ws_manager import NotifyPayload, notify_admin
from datetime import datetime
from sqlalchemy.orm import Session
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

@router.get("/users", response_class=JSONResponse)
def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    """
    ✅ ดึงข้อมูลผู้ใช้ทั้งหมดสำหรับจัดการบทบาทและตำแหน่ง
    """
    users = db.query(User).all()
    user_data = [{"id": user.id, "name": user.name, "role": user.role, "position": user.position} for user in users]
    return user_data

    """
    ✅ ดึงข้อมูลผู้ใช้ทั้งหมดสำหรับจัดการบทบาท
    """
    users = db.query(User).all()
    user_data = [{"id": user.id, "name": user.name, "role": user.role} for user in users]
    return user_data

@router.put("/users/{user_id}/update-role", response_class=JSONResponse)
def update_user_role(
    user_id: int,
    role_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    new_role = role_data.get("role")
    if not new_role or new_role not in ["customer", "employee"]:
        raise HTTPException(status_code=400, detail="❌ Invalid role specified")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="❌ User not found")
    
    user.role = new_role
    db.commit()
    return {"message": f"✅ บทบาทของผู้ใช้ {user_id} ถูกอัปเดตเป็น {new_role}"}

    """
    ✅ อัปเดตบทบาทของผู้ใช้
    """
    new_role = role_data.get("role")
    if new_role not in ["admin", "packing staff", "preparation staff"]:
        raise HTTPException(status_code=400, detail="❌ Invalid role specified")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="❌ User not found")

    user.role = "employee"
    user.position = new_role
    db.commit()

    return {"message": f"✅ บทบาทของผู้ใช้ {user_id} ถูกอัปเดตเป็น {new_role}"}

@router.put("/users/{user_id}/update-position", response_class=JSONResponse)
def update_user_position(
    user_id: int,
    position_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    """
    ✅ อัปเดตตำแหน่ง (Position) ของผู้ใช้
    """
    new_position = position_data.get("position")
    valid_positions = ["admin", "preparation staff", "packing staff"]

    if new_position not in valid_positions:
        raise HTTPException(status_code=400, detail="❌ Invalid position specified")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="❌ User not found")

    user.position = new_position
    db.commit()

    return {"message": f"✅ ตำแหน่งของผู้ใช้ {user_id} ถูกอัปเดตเป็น {new_position}"}


@router.delete("/users/{user_id}", response_class=JSONResponse)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    """
    ✅ ลบผู้ใช้จากระบบ
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="❌ User not found")

    db.delete(user)
    db.commit()
    
    return {"message": f"✅ ผู้ใช้ {user_id} ถูกลบสำเร็จ"}


# Route สำหรับแสดงหน้าจัดการroles
@router.get("/roles", response_class=HTMLResponse)
def get_order_management(
    request: Request,
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    print(f"🛡️ Order Management Access by: {current_user.email}")
    return templates.TemplateResponse("admin_roles.html", {"request": request, "current_user": current_user})

# Route สำหรับแสดงหน้าจัดการ
@router.get("/working-status", response_class=HTMLResponse)
def get_working_logs(
    request: Request,
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    print(f"🛡️ Order Management Access by: {current_user.email}")
    return templates.TemplateResponse("admin_logs.html", {"request": request, "current_user": current_user})


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

@router.get("/work-status", response_class=JSONResponse)
def get_work_status(
    date: str,  # รับวันที่ที่ต้องการดูข้อมูล เช่น "2024-02-01"
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    """
    ✅ ดึงสถานะการทำงานของพนักงานแต่ละโต๊ะตามวันที่
    """
    orders = db.query(Order).filter(and_(
        Order.created_at >= f"{date} 00:00:00",
        Order.created_at <= f"{date} 23:59:59"
    )).all()

    order_data = [
        {
            "order_id": order.order_id,
            "table_number": order.camera.table_number if order.camera else "N/A",
            "employee_name": order.user.name if order.user else "N/A",
            "status": order.status,  # เช่น pending, packing, completed
            "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        for order in orders
    ]
    return {"work_status": order_data}

@router.get("/my-work-status", response_class=JSONResponse)
def get_my_work_status(
    date: str,  # รับวันที่ที่ต้องการดูข้อมูล
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ให้พนักงานทุกตำแหน่งเข้าถึง
):
    """
    ✅ ให้พนักงานดูสถานะของตนเองในแต่ละวัน
    """
    try:
        # แปลงวันที่เป็น datetime object เพื่อให้การค้นหาแม่นยำขึ้น
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        start_date = date_obj.replace(hour=0, minute=0, second=0)
        end_date = date_obj.replace(hour=23, minute=59, second=59)

        # ดึงข้อมูลกล้องที่ถูก assign ให้พนักงานนี้
        assigned_camera = db.query(Camera).filter(Camera.assigned_to == current_user.id).first()
        table_number = assigned_camera.table_number if assigned_camera else "N/A"

        # ดึงข้อมูล orders ของพนักงาน
        orders = (
            db.query(Order)
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
            # แปลงข้อมูล JSON string เป็น dict
            try:
                items = json.loads(order.item) if order.item else {}
                item_count = len(items)
            except json.JSONDecodeError:
                items = {}
                item_count = 0

            order_data.append({
                "order_id": order.order_id,
                "table_number": table_number,  # ใช้หมายเลขโต๊ะจากกล้องที่ถูก assign
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

    except ValueError:
        raise HTTPException(status_code=400, detail="รูปแบบวันที่ไม่ถูกต้อง กรุณาใช้รูปแบบ YYYY-MM-DD")
    except Exception as e:
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



# Camera Management Routes
@router.get("/cameras", response_class=HTMLResponse)
async def get_cameras_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    """หน้าจัดการกล้อง"""
    cameras = camera_crud.get_cameras(db)
    employees = user_crud.get_users_by_role(db, "employee")  # ดึงรายชื่อพนักงานทั้งหมด
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
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    """ดึงข้อมูลกล้องทั้งหมด"""
    return camera_crud.get_cameras(db)

@router.post("/api/cameras", response_model=CameraSchema)
async def create_camera(
    camera: CameraCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    """สร้างกล้องใหม่"""
    db_camera = camera_crud.create_camera(db, camera)
    if not db_camera:
        raise HTTPException(status_code=400, detail="หมายเลขโต๊ะนี้มีกล้องใช้งานอยู่แล้ว")
    return db_camera

@router.put("/api/cameras/{camera_id}", response_model=CameraSchema)
async def update_camera(
    camera_id: int,
    camera: CameraUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
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
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    """ลบกล้อง"""
    if not camera_crud.delete_camera(db, camera_id):
        raise HTTPException(status_code=404, detail="ไม่พบกล้องที่ต้องการ")
    return {"status": "success", "message": "ลบกล้องเรียบร้อยแล้ว"}
