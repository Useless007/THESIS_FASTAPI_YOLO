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
from app.models.account import Account
from app.database import get_db
from app.services.auth import get_current_user, verify_password, hash_password, authenticate_account
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

# สร้าง Routers ใหม่สำหรับการลงทะเบียนของลูกค้าและพนักงาน
customer_router = APIRouter(prefix="/customer", tags=["Customer Registration"])
employee_router = APIRouter(prefix="/employee", tags=["Employee Registration"])

# เพิ่ม customer_router และ employee_router เข้ากับ router หลัก
router.include_router(customer_router)
router.include_router(employee_router)

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
    ตรวจสอบทั้ง User (พนักงาน) และ Customer (ลูกค้า)
    """
    # ใช้ฟังก์ชันใหม่สำหรับตรวจสอบการเข้าสู่ระบบที่ใช้ Account เป็นศูนย์กลาง
    account, is_customer = authenticate_account(username, password, db)
    
    if not account:
        # ไม่พบผู้ใช้หรือรหัสผ่านไม่ถูกต้อง
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "message": "❌ ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง",
                "message_color": "red"
            }
        )
    
    # สร้าง Token สำหรับผู้ใช้
    access_token = create_access_token(data={"sub": account.email}, is_customer=is_customer)
    
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="Authorization",
        value=f"Bearer {access_token}",
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
    # ตรวจสอบ email/password โดยใช้ Account
    account, is_customer = authenticate_account(form_data.username, form_data.password, db)
    if not account:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    # สร้างและส่ง JWT token
    access_token = create_access_token(data={"sub": account.email}, is_customer=is_customer)
    return {"access_token": access_token, "token_type": "bearer"}

@protected_router.get("/register", response_class=HTMLResponse, tags=["HTML"])
def get_register_form(request: Request):
    """
    แสดงฟอร์ม HTML สำหรับการลงทะเบียน
    """
    return templates.TemplateResponse("register.html", {"request": request})

@protected_router.get("/employee-register", response_class=HTMLResponse)
def get_employee_register_form(request: Request):
    """
    แสดงหน้าลงทะเบียนพนักงาน
    """
    return templates.TemplateResponse("register_employee.html", {"request": request})

@protected_router.get("/settings", response_class=HTMLResponse, tags=["HTML"])
def get_register_form(request: Request, current_user: User = Depends(get_current_user)):
    """
    แสดงฟอร์มการตั้งค่าบัญชี
    """
    return templates.TemplateResponse("setting.html", {"request": request})


@protected_router.post("/register", response_class=HTMLResponse)
def post_customer_register_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    phone: str = Form(None),
    db: Session = Depends(get_db),
):
    """
    รับข้อมูลจากฟอร์มและสร้างลูกค้าใหม่ในฐานข้อมูล พร้อมเข้าสู่ระบบอัตโนมัติและเปลี่ยนเส้นทางไปที่หน้าหลัก
    ลูกค้าสามารถเข้าสู่ระบบได้ทันทีโดยไม่ต้องรอการอนุมัติ
    """
    from app.crud.customer import create_customer
    from app.schemas.customer import CustomerCreate
    
    customer_data = CustomerCreate(
        email=email,
        password=password,
        name=name,
        phone=phone,
        is_active=True  # ตั้งค่าให้ลูกค้าเป็น active ทันที
    )
    try:
        # สร้างลูกค้าใหม่
        db_customer = create_customer(db=db, customer=customer_data)
        
        # สร้าง Token สำหรับลูกค้า (ไม่ต้องใช้บทบาทเพิ่มเติม)
        token_data = {"sub": email}
        token = create_access_token(token_data, is_customer=True)  # ระบุว่าเป็น customer
        
        # สร้าง Response เป็น redirect ไปหน้าหลัก
        response = RedirectResponse(url="/", status_code=303)
        
        # เพิ่ม cookie สำหรับ Authorization
        response.set_cookie(
            key="Authorization",
            value=f"Bearer {token}",
            httponly=False,  # False เพื่อให้ JavaScript อ่านได้
            secure=False,    # เปลี่ยนเป็น True บน HTTPS
            samesite="Lax",
            max_age=3600,
            path="/"  # ✅ สำคัญ: ให้ Cookie มีผลกับทุกเส้นทาง
        )
        return response

    except IntegrityError as e:
        if "Duplicate entry" in str(e.orig):
            message = "❌ Email นี้มีอยู่ในระบบแล้ว"
        else:
            message = f"❌ เกิดข้อผิดพลาด: {str(e.orig)}"
            
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": message}
        )

@protected_router.post("/employee-register", response_class=HTMLResponse)
def post_employee_register_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    phone: str = Form(None),
    # Address fields
    house_number: str = Form(...),
    village_no: str = Form(None),
    subdistrict: str = Form(...),
    district: str = Form(...),
    province: str = Form(...),
    postal_code: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    รับข้อมูลจากฟอร์มและสร้างพนักงานใหม่ในฐานข้อมูล พร้อมข้อมูลที่อยู่
    พนักงานต้องรอการอนุมัติจากแอดมินก่อนเข้าสู่ระบบได้
    """
    from app.crud.user import create_user
    from app.schemas.user import UserCreate
    from app.models.address import Address
    
    user_data = UserCreate(
        email=email,
        password=password,
        name=name,
        phone=phone,
        role_id=1,  # 1 = employee
        position_id=1,  # default position
        is_active=False  # เริ่มต้นเป็น inactive รอการอนุมัติ
    )
    try:
        # สร้างพนักงานใหม่
        db_user = create_user(db=db, user=user_data)
        
        # สร้างข้อมูลที่อยู่และเชื่อมกับ user_id
        new_address = Address(
            user_id=db_user.id,
            house_number=house_number,
            village_no=village_no,
            subdistrict=subdistrict,
            district=district,
            province=province,
            postal_code=postal_code
        )
        db.add(new_address)
        db.commit()
        
        # ส่งกลับหน้ารอการอนุมัติจากแอดมิน
        return templates.TemplateResponse(
            "register_employee_success.html",
            {
                "request": request, 
                "message": "✅ ลงทะเบียนสำเร็จ กรุณารอการอนุมัติจากแอดมินก่อนเข้าสู่ระบบ", 
                "name": name
            }
        )

    except IntegrityError as e:
        if "Duplicate entry" in str(e.orig):
            message = "❌ Email นี้มีอยู่ในระบบแล้ว"
        else:
            message = f"❌ เกิดข้อผิดพลาด: {str(e.orig)}"
            
        return templates.TemplateResponse(
            "register_employee.html",
            {"request": request, "error": message}
        )
    except Exception as e:
        message = f"❌ เกิดข้อผิดพลาด: {str(e)}"
        return templates.TemplateResponse(
            "register_employee.html",
            {"request": request, "error": message}
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
        if current_user.role_id != int(role):
            return {"status": "error", "message": f"Requires role: {role}"}
    
    if position:
        if current_user.position_id != int(position):
            return {"status": "error", "message": f"Requires position: {position}"}
    
    return {
        "status": "success",
        "role": current_user.role_id,
        "position": current_user.position_id,
        "is_active": current_user.is_active
    }



# ---------------------------------------------------------------------
# PUBLIC USER ENDPOINTS
# ---------------------------------------------------------------------

@router.get("/profile")
def get_user_profile(request: Request, db: Session = Depends(get_db)):
    """
    ดึงข้อมูลโปรไฟล์ของผู้ใช้ทั้งลูกค้าและพนักงาน
    """
    from app.services.auth import get_current_actor
    from app.models.customer import Customer
    
    # ดึงข้อมูลผู้ใช้ปัจจุบัน (ทั้งลูกค้าและพนักงาน)
    current_actor = get_current_actor(request, db)
    
    if not current_actor:
        raise HTTPException(status_code=401, detail="ไม่พบข้อมูลผู้ใช้")
    
    # ตรวจสอบว่าเป็น Customer หรือ User
    is_customer = isinstance(current_actor, Customer)
    
    # ดึงข้อมูล Account ที่เชื่อมโยงกับ actor
    account = db.query(Account).filter(Account.id == current_actor.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลบัญชี")
    
    address_info = None
    
    # ดึงข้อมูลที่อยู่ตามประเภทของผู้ใช้
    if is_customer:
        # ดึงที่อยู่ของลูกค้า
        from app.models.address import Address
        address = db.query(Address).filter(Address.customer_id == current_actor.id).first()
        
        if address:
            address_info = {
                "house_number": address.house_number,
                "village_no": address.village_no,
                "subdistrict": address.subdistrict,
                "district": address.district,
                "province": address.province,
                "postal_code": address.postal_code,
                "full_address": f"{address.house_number} หมู่ {address.village_no} ต.{address.subdistrict} อ.{address.district} จ.{address.province} {address.postal_code}"
            }
    else:
        # ดึงที่อยู่ของพนักงาน (User)
        if hasattr(current_actor, 'addresses') and current_actor.addresses:
            # ดึงที่อยู่แรกจาก list (ถ้ามีหลายที่อยู่)
            address = current_actor.addresses[0]
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
        "name": account.name,
        "email": account.email,
        "phone": account.phone,
        "address": address_info,  # ส่งข้อมูลที่อยู่แบบ object
        "is_customer": is_customer
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
    # ดึงข้อมูล Account ที่เชื่อมโยงกับผู้ใช้
    account = db.query(Account).filter(Account.id == current_user.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="ไม่พบข้อมูลบัญชี")
    
    # ตรวจสอบรหัสผ่านปัจจุบัน
    if not verify_password(current_password, account.password):
        raise HTTPException(status_code=400, detail="รหัสผ่านปัจจุบันไม่ถูกต้อง")
    
    # อัปเดตรหัสผ่านใหม่
    account.password = hash_password(new_password)  # hash รหัสผ่านใหม่ก่อนบันทึก
    db.commit()
    
    return {"status": "success", "message": "รีเซ็ตรหัสผ่านสำเร็จ"}
