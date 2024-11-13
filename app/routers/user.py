# routers/user.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.models.user import User
from app.database import get_db
from app.schemas.user import UserCreate, UserUpdate, UserOut
from app.crud.user import create_user, get_user_by_id, get_all_users, update_user, delete_user, update_user_status
from app.services.auth import create_access_token, get_current_user, get_user_with_role, get_user_with_role_and_position, verify_password, oauth2_scheme
from fastapi.security import OAuth2PasswordRequestForm


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

admin_router = APIRouter(
    tags=["Admin"],
    dependencies=[Depends(get_user_with_role_and_position("employee", "admin"))]
)

protected_router = APIRouter(
    tags=["Auth"],
)

# ฟังก์ชันสำหรับการ login
@protected_router.post("/login")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    username: ให้ใช้ email ส่วน password ให้ใช้ password ที่สร้างไว้
    """
    # ค้นหาผู้ใช้จากฐานข้อมูลด้วย email หรือ username
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.password):  # ตรวจสอบ password
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )
    
    # อัปเดตสถานะผู้ใช้ให้เป็น active
    update_user_status(db, user.id, True)
    
    # สร้าง JWT token
    access_token = create_access_token(data={"sub": user.email})  # ใช้ email ของ user ใน payload
    return {"access_token": access_token, "token_type": "bearer"}

# สร้าง User ใหม่
@router.post("/", response_model=UserOut)
def create_new_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    ใช้สำหรับสร้างUser ใหม่ และ Employee ใหม่
    """
    db_user = create_user(db=db, user=user)
    if db_user:
        return db_user
    raise HTTPException(status_code=400, detail="User creation failed")

# ดึงข้อมูล User ด้วย ID
@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """
    ใช้สำหรับดึงข้อมูล User ด้วย ID
    """
    db_user = get_user_by_id(db=db, user_id=user_id)
    if db_user:
        return db_user
    raise HTTPException(status_code=404, detail="User not found")

# ดึงข้อมูล User ทั้งหมด
@router.get("/", response_model=List[UserOut], tags=["Admin"])
def get_users(db: Session = Depends(get_db), current_user=Depends(get_user_with_role_and_position("employee", "admin"))):
    """
    ใช้สำหรับดึงข้อมูล User ทั้งหมด
    """
    return get_all_users(db=db)

# อัปเดตข้อมูล User
@router.put("/{user_id}", response_model=UserOut)
def update_user_info(user_id: int, user: UserUpdate, db: Session = Depends(get_db)):
    db_user = update_user(db=db, user_id=user_id, user=user)
    if db_user:
        return db_user
    raise HTTPException(status_code=404, detail="User not found")

# ลบ User ด้วย ID
@router.delete("/{user_id}", response_model=UserOut, tags=["Admin"])
def delete_user_info(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_user_with_role_and_position("employee", "admin"))):
    """
    ใช้สำหรับลบ User ด้วย ID
    """
    db_user = delete_user(db=db, user_id=user_id)
    if db_user:
        return db_user
    raise HTTPException(status_code=404, detail="User not found")

# เปิดใช้งานผู้ใช้โดย ID สิทธิ์ admin เท่านั้น
@admin_router.put("/{user_id}/activate", response_model=UserOut)
def activate_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_user_with_role_and_position("employee", "admin"))):
    """
    Admin ใช้สำหรับเปิดใช้งานผู้ใช้
    """
    db_user = get_user_by_id(db=db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # เปลี่ยนสถานะผู้ใช้เป็น active
    updated_user = update_user_status(db=db, user_id=user_id, is_active=True)
    return updated_user

# ปิดใช้งานผู้ใช้โดย ID สิทธิ์ admin เท่านั้น
@admin_router.put("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_user_with_role_and_position("employee", "admin"))):
    """
    Admin ใช้สำหรับปิดใช้งานผู้ใช้
    """
    db_user = get_user_by_id(db=db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # เปลี่ยนสถานะผู้ใช้เป็น inactive
    updated_user = update_user_status(db=db, user_id=user_id, is_active=False)
    return updated_user