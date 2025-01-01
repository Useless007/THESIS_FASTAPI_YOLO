from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.models.user import User
from app.services.auth import get_user_with_role_and_position_and_isActive
from app.database import get_db
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(prefix="/admin", tags=["Admin"])

# Route สำหรับแสดงหน้า Admin Dashboard
@router.get("/dashboard", response_class=HTMLResponse)
def get_admin_dashboard(
    request: Request,
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    print(f"🛡️ Admin Dashboard Access by: {current_user.email}")
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, "current_user": current_user})

# Route สำหรับดึงข้อมูลแดชบอร์ด
@router.get("/dashboard-data")
def get_dashboard_data(
    db: Session = Depends(get_db),
    current_user = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    # ตัวอย่างข้อมูล
    return {
        "user_count": db.query(User).count(),
        "sales_today": 1500  # แสดงยอดขายวันนี้
    }


@router.get("/activate", response_class=HTMLResponse)
def get_user_management(
    request: Request,
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    print(f"🛡️ Activate Management Access by: {current_user.email}")
    return templates.TemplateResponse("admin_activate.html", {"request": request, "current_user": current_user})


# Route สำหรับดึงข้อมูลผู้ใช้ที่ต้องการ Activate
@router.get("/employees-to-activate", response_class=JSONResponse)
def get_users_to_activate(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin"))
):
    users = db.query(User).filter(User.is_active == False, User.role == "employee").all()
    return users