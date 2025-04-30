# app/routers/user.py

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy.exc import IntegrityError
from fastapi.responses import RedirectResponse
from typing import Optional

from app.models.user import User
from app.database import get_db
from app.services.auth import get_current_user, verify_password, hash_password
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
)

# เพิ่ม Jinja2 Templates
templates = Jinja2Templates(directory="app/templates")


# ตั้งค่า Routers
router = APIRouter(prefix="/users", tags=["Users"])
admin_router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(get_user_with_role_and_position(1, 2))],
)
protected_router = APIRouter(tags=["Auth"])

# ---------------------------------------------------------------------
# AUTH ENDPOINTS
# ---------------------------------------------------------------------
@protected_router.get("/login", response_class=HTMLResponse, tags=["HTML"])
def get_login_form(request: Request):
    """
    แสดงฟอร์ม HTML สำหรับการเข้าสู่ระบบ
    """
    return templates.TemplateResponse("login.html", {"request": request})

# TODO: ทำให้ใช้ร่่วมกับ JWT และแสดงข็อความlogout บนnavbar
# @router.post("/login")
@protected_router.post("/login", response_class=HTMLResponse)
def authenticate_user_and_generate_token(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    ตรวจสอบข้อมูลการเข้าสู่ระบบและส่ง Token กลับ
    """
    user = db.query(User).filter(User.email == username).first()
    
    if not user or not verify_password(password, user.password):
        # หาก username หรือ password ไม่ถูกต้อง
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "message": "❌ ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง",
                "message_color": "red"
            }
        )

    # หากตรวจสอบผ่าน สร้าง Token
    access_token = create_access_token(data={"sub": user.email})
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="Authorization",
        value=f"Bearer {access_token}",
        # domain=".jintaphas.tech", # อนุญาตให้ทุก subdomain ใช้ Cookies ได้
        httponly=False,  # False เพื่อให้ JavaScript อ่านได้
        secure=False,   # เปลี่ยนเป็น True บน HTTPS
        samesite="Lax",
        max_age=3600,
        path="/"  # ✅ สำคัญ: ให้ Cookie มีผลกับทุกเส้นทาง
    )
    return response

@protected_router.post("/getToken")
def authenticate_user_and_generate_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Endpoint สำหรับเข้าสู่ระบบและสร้าง JWT token
    """
    # ตรวจสอบ email/password
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    # อัปเดตสถานะเป็น active
    # update_user_status(db, user.id, True)

    # สร้างและส่ง JWT token
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@protected_router.get("/register", response_class=HTMLResponse, tags=["HTML"])
def get_register_form(request: Request):
    """
    แสดงฟอร์ม HTML สำหรับการลงทะเบียน
    """
    return templates.TemplateResponse("register.html", {"request": request})

@protected_router.get("/settings", response_class=HTMLResponse, tags=["HTML"])
def get_register_form(request: Request, current_user: User = Depends(get_current_user)):
    """
    แสดงฟอร์มการตั้งค่าบัญชี
    """
    return templates.TemplateResponse("setting.html", {"request": request})


@protected_router.post("/register", response_class=HTMLResponse)
def post_register_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    รับข้อมูลจากฟอร์มและสร้างผู้ใช้ใหม่ในฐานข้อมูล พร้อมเข้าสู่ระบบอัตโนมัติ
    """
    user_data = UserCreate(
        email=email,
        password=password,
        name=name,
        role_id=2,  # 2 = customer
        is_active=False
    )
    try:
        # สร้างผู้ใช้ใหม่
        create_user(db=db, user=user_data)

        # สร้าง JWT Token สำหรับผู้ใช้ที่ลงทะเบียนสำเร็จ
        access_token = create_access_token(data={"sub": email})

        # ตั้งค่า Cookie พร้อม Redirect ไปหน้า Home
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key="Authorization",
            value=f"Bearer {access_token}",
            # domain=".jintaphas.tech", # อนุญาตให้ทุก subdomain ใช้ Cookies ได้
            httponly=False,  # False เพื่อให้ JavaScript อ่านได้
            secure=False,   # True ถ้าใช้ HTTPS
            samesite="Lax",
            max_age=3600,
            path="/"  # ✅ สำคัญ: ให้ Cookie มีผลกับทุกเส้นทาง
        )
        return response

    except IntegrityError as e:
        if "Duplicate entry" in str(e.orig):
            message = "❌ Email นี้มีอยู่ในระบบแล้ว"
        else:
            message = f"❌ Registration failed due to a database error: {str(e)}"
        message_color = "red"
    except Exception as e:
        message = f"❌ Registration failed due to an unexpected error: {str(e)}"
        message_color = "red"

    return templates.TemplateResponse(
        "register.html", 
        {"request": request, "message": message, "message_color": message_color}
    )
    
    
@protected_router.get("/role-check", tags=["Auth"])
def check_user_role(
    role: Optional[str] = None,
    position: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user)
):
    
    """
    ตรวจสอบบทบาทและสถานะของผู้ใช้
    - ถ้าไม่มี Token ให้ส่งสถานะเป็น Guest
    """
    if current_user is None:
        return {
            "status": "guest",
            "message": "Guest user",
        }
    
    """
    ตรวจสอบบทบาทและตำแหน่งของผู้ใช้
    - role: ระบุบทบาทที่ต้องการตรวจสอบ (customer, employee)
    - position: ระบุตำแหน่งพนักงาน (admin, preparation staff, packing staff)
    """
    if not current_user:
        return {"status": "success", "message": "Guest user"}
    
    if role:
        if current_user.role != role:
            return {"status": "error", "message": f"Requires role: {role}"}
    
    if position:
        if current_user.position != position:
            return {"status": "error", "message": f"Requires position: {position}"}
    
    return {
        "status": "success",
        "role": current_user.role,
        "position": current_user.position,
        "is_active": current_user.is_active
    }



# ---------------------------------------------------------------------
# PUBLIC USER ENDPOINTS
# ---------------------------------------------------------------------

@router.get("/profile")
def get_user_profile(current_user: User = Depends(get_current_user)):
    # ดึงข้อมูลที่อยู่จาก relationship ถ้ามี
    address_info = None
    if current_user.addresses:
        # ดึงที่อยู่แรกจาก list (ถ้ามีหลายที่อยู่)
        address = current_user.addresses[0]
        address_info = {
            "house_number": address.house_number,
            "village_no": address.village_no,
            "subdistrict": address.subdistrict,
            "district": address.district,
            "province": address.province,
            "postal_code": address.postal_code,
            "full_address": f"{address.house_number} หมู่ {address.village_no} ต.{address.subdistrict} อ.{address.district} จ.{address.province} {address.postal_code}"
        }
    
    return {
        "name": current_user.name,
        "phone": current_user.phone,
        "address": address_info  # ส่งข้อมูลที่อยู่แบบ object
    }



@router.post("/", response_model=UserOut)
def create_new_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    สร้าง User ใหม่
    """
    db_user = create_user(db=db, user=user)
    if db_user:
        return db_user
    raise HTTPException(status_code=400, detail="User creation failed")

@router.get("/{user_id}", response_model=UserOut,tags=["Admin"])
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))
    ):
    
    """
    ดึงข้อมูล User โดยใช้ user_id
    """
    db_user = get_user_by_id(db=db, user_id=user_id)
    if db_user:
        return db_user
    raise HTTPException(status_code=404, detail="User not found")

@router.put("/{user_id}", response_model=UserOut)
def update_user_info(user_id: int, user: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2))):
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
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2)),
):
    """
    ดึงข้อมูล User ทั้งหมด (Admin Only)
    """
    return get_all_users(db=db)

@admin_router.put("/{user_id}/activate")
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2)),
):
    """
    เปิดใช้งาน User (Admin Only)
    """
    db_user = get_user_by_id(db=db, user_id=user_id)
    
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # print(f"🔄 Activating user: {db_user.email}")
    return update_user_status(db=db, user_id=user_id, is_active=True)

@admin_router.put("/{user_id}/deactivate")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2)),
):
    """
    ปิดใช้งาน User (Admin Only)
    """
    db_user = get_user_by_id(db=db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return update_user_status(db=db, user_id=user_id, is_active=False)

@admin_router.delete("/{user_id}")
def delete_user_info(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 2)),
):
    """
    ลบ User (Admin Only)
    """
    db_user = delete_user(db=db, user_id=user_id)
    if db_user:
        return db_user
    raise HTTPException(status_code=404, detail="User not found")


@protected_router.post("/reset-password")
def reset_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    รีเซ็ตรหัสผ่านของผู้ใช้
    """
    # ตรวจสอบรหัสผ่านปัจจุบัน
    if not verify_password(current_password, current_user.password):
        raise HTTPException(status_code=400, detail="รหัสผ่านปัจจุบันไม่ถูกต้อง")
    
    # อัปเดตรหัสผ่านใหม่
    user = db.query(User).filter(User.id == current_user.id).first()
    user.password = hash_password(new_password)  # hash รหัสผ่านใหม่ก่อนบันทึก
    db.commit()
    
    return {"status": "success", "message": "รีเซ็ตรหัสผ่านสำเร็จ"}
