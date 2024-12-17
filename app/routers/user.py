# app/routers/user.py
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.database import get_db
from app.schemas.user import UserCreate, UserUpdate, UserOut
from app.crud.user import (
    create_user,
    get_user_by_id,
    get_all_users,
    update_user,
    delete_user,
    update_user_status,
)
from app.services.auth import (
    create_access_token,
    get_user_with_role_and_position,
    get_user_with_role_and_position_and_isActive,
    verify_password,
)

# เพิ่ม Jinja2 Templates
templates = Jinja2Templates(directory="app/templates")


# ตั้งค่า Routers
router = APIRouter(prefix="/users", tags=["Users"])
admin_router = APIRouter(
    tags=["Admin"],
    dependencies=[Depends(get_user_with_role_and_position("employee", "admin"))],
)
protected_router = APIRouter(tags=["Auth"])

# ---------------------------------------------------------------------
# AUTH ENDPOINTS
# ---------------------------------------------------------------------
@protected_router.post("/login")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Endpoint สำหรับเข้าสู่ระบบและสร้าง JWT token
    """
    # ตรวจสอบ email/password
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    # อัปเดตสถานะเป็น active
    update_user_status(db, user.id, True)

    # สร้างและส่ง JWT token
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@protected_router.get("/register", response_class=HTMLResponse)
def get_register_form(request: Request):
    """
    แสดงฟอร์ม HTML สำหรับการลงทะเบียน
    """
    return templates.TemplateResponse("register.html", {"request": request})


@protected_router.post("/register", response_class=HTMLResponse)
def post_register_form(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    รับข้อมูลจากฟอร์มและสร้างผู้ใช้ใหม่ในฐานข้อมูล
    """
    user_data = UserCreate(
        username=username,
        email=email,
        password=password,
        name=name,
        role="customer",  # กำหนดบทบาทเป็น customer
    )
    try:
        create_user(db=db, user=user_data)
        message = "User registered successfully!"
        message_color = "green"
    except IntegrityError as e:
        # ตรวจสอบว่าเป็น Duplicate Entry หรือไม่
        if "Duplicate entry" in str(e.orig):
            message = "Email หรือ Username นี้มีอยู่ในระบบแล้ว"
        else:
            message = "Registration failed due to a database error."
        message_color = "red"
    except Exception:
        message = "Registration failed due to an unexpected error."
        message_color = "red"
    
    return templates.TemplateResponse(
        "register.html", 
        {"request": request, "message": message, "message_color": message_color}
    )

# ---------------------------------------------------------------------
# PUBLIC USER ENDPOINTS
# ---------------------------------------------------------------------
@router.post("/", response_model=UserOut)
def create_new_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    สร้าง User ใหม่
    """
    db_user = create_user(db=db, user=user)
    if db_user:
        return db_user
    raise HTTPException(status_code=400, detail="User creation failed")

@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """
    ดึงข้อมูล User โดยใช้ user_id
    """
    db_user = get_user_by_id(db=db, user_id=user_id)
    if db_user:
        return db_user
    raise HTTPException(status_code=404, detail="User not found")

@router.put("/{user_id}", response_model=UserOut)
def update_user_info(user_id: int, user: UserUpdate, db: Session = Depends(get_db)):
    """
    อัปเดตข้อมูล User
    """
    db_user = update_user(db=db, user_id=user_id, user=user)
    if db_user:
        return db_user
    raise HTTPException(status_code=404, detail="User not found")

# ---------------------------------------------------------------------
# ADMIN ONLY ENDPOINTS
# ---------------------------------------------------------------------
@router.get("/", response_model=List[UserOut], tags=["Admin"])
def get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin")),
):
    """
    ดึงข้อมูล User ทั้งหมด (Admin Only)
    """
    return get_all_users(db=db)

@admin_router.put("/{user_id}/activate", response_model=UserOut)
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin")),
):
    """
    เปิดใช้งาน User (Admin Only)
    """
    db_user = get_user_by_id(db=db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return update_user_status(db=db, user_id=user_id, is_active=True)

@admin_router.put("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin")),
):
    """
    ปิดใช้งาน User (Admin Only)
    """
    db_user = get_user_by_id(db=db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return update_user_status(db=db, user_id=user_id, is_active=False)

@admin_router.delete("/{user_id}", response_model=UserOut)
def delete_user_info(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "admin")),
):
    """
    ลบ User (Admin Only)
    """
    db_user = delete_user(db=db, user_id=user_id)
    if db_user:
        return db_user
    raise HTTPException(status_code=404, detail="User not found")
