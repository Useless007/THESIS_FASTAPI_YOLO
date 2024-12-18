# app/crud/user.py

from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth import verify_password, hash_password
from fastapi import HTTPException


def create_user(db: Session, user: UserCreate):
    # แฮชรหัสผ่านก่อนบันทึก
    hashed_password = hash_password(user.password)
    
    db_user = User(
        # username=user.username,
        email=user.email,
        password=hashed_password,
        name=user.name,
        role=user.role,  # ระบุบทบาท (customer, admin, staff)
        address=user.address,
        position=user.position,
        phone=user.phone,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# ฟังก์ชันดึงข้อมูล User ด้วย ID
def get_user_by_id(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

# ฟังก์ชันดึงข้อมูล User ด้วย email
def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

# ฟังก์ชันดึงข้อมูล User ทั้งหมด (ใช้เพื่อค้นหาหรือแสดงรายชื่อทั้งหมด)
def get_all_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(User).offset(skip).limit(limit).all()

# ฟังก์ชันอัปเดตข้อมูล User
def update_user(db: Session, user_id: int, user: UserUpdate):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        return None

    # แฮชรหัสผ่านหากมีการอัปเดต
    if user.password:
        hashed_password = hash_password(user.password)

    # อัปเดตฟิลด์ต่างๆ
    # db_user.username = user.username or db_user.username
    db_user.email = user.email or db_user.email
    db_user.password = hashed_password or db_user.password
    db_user.name = user.name or db_user.name
    db_user.address = user.address or db_user.address
    db_user.phone = user.phone or db_user.phone
    db_user.role = user.role or db_user.role
    db_user.position = user.position or db_user.position
    db.commit()
    db.refresh(db_user)
    return db_user

# ฟังก์ชันลบ User ด้วย ID
def delete_user(db: Session, user_id: int):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        return None
    db.delete(db_user)
    db.commit()
    return db_user

# อนุญาติให้ผู้ใช้เข้าถึงระบบ
def update_user_status(db: Session, user_id: int, is_active: bool):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        return None
    db_user.is_active = is_active
    db.commit()
    db.refresh(db_user)
    return db_user
