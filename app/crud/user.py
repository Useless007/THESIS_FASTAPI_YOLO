# app/crud/user.py

from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth import verify_password, hash_password
from fastapi import HTTPException
from datetime import datetime


def create_user(db: Session, user: UserCreate):
    # แฮชรหัสผ่านก่อนบันทึก
    hashed_password = hash_password(user.password)
    
    db_user = User(
        email=user.email,
        password=hashed_password,
        name=user.name,
        role_id=user.role_id,  # ใช้ role_id แทน role
        position_id=user.position_id,  # ใช้ position_id แทน position
        phone=user.phone,
        created_at=datetime.utcnow(),
        is_active=False
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
        db_user.password = hashed_password

    # อัปเดตฟิลด์ต่างๆ
    if user.email:
        db_user.email = user.email
    if user.name:
        db_user.name = user.name
    if user.phone:
        db_user.phone = user.phone
    if user.role_id:
        db_user.role_id = user.role_id
    if user.position_id:
        db_user.position_id = user.position_id
    if user.is_active is not None:
        db_user.is_active = user.is_active
    
    db_user.updated_at = datetime.utcnow()
    
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
    db_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_user)
    return db_user

# ดึงข้อมูลผู้ใช้ตามบทบาท
def get_users_by_role(db: Session, role_id: int):
    return db.query(User).filter(User.role_id == role_id, User.is_active == True).all()