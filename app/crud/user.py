# app/crud/user.py

from sqlalchemy.orm import Session
from app.models.user import User
from app.models.account import Account
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth import verify_password, hash_password
from fastapi import HTTPException
from datetime import datetime


def create_user(db: Session, user: UserCreate):
    # แฮชรหัสผ่านก่อนบันทึก
    hashed_password = hash_password(user.password)
    
    # สร้าง Account ก่อน
    db_account = Account(
        email=user.email,
        password=hashed_password,
        name=user.name,
        phone=user.phone,
        created_at=datetime.utcnow(),
        is_active=False  # พนักงานเริ่มต้นเป็น inactive จนกว่าจะยืนยัน
    )
    db.add(db_account)
    db.flush()  # ใช้ flush เพื่อให้ได้ id ของ account
    
    # สร้าง User ที่เชื่อมโยงกับ Account
    db_user = User(
        account_id=db_account.id,
        role_id=user.role_id,
        position_id=user.position_id,
        created_at=datetime.utcnow()
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
    return db.query(User)\
             .join(Account, Account.id == User.account_id)\
             .filter(Account.email == email)\
             .first()

# ฟังก์ชันดึงข้อมูล User ทั้งหมด (ใช้เพื่อค้นหาหรือแสดงรายชื่อทั้งหมด)
def get_all_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(User).offset(skip).limit(limit).all()

# ฟังก์ชันอัปเดตข้อมูล User
def update_user(db: Session, user_id: int, user: UserUpdate):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        return None
        
    # ดึง Account ที่เชื่อมโยงกับ User
    db_account = db.query(Account).filter(Account.id == db_user.account_id).first()
    if not db_account:
        return None

    # แฮชรหัสผ่านหากมีการอัปเดต
    if user.password:
        hashed_password = hash_password(user.password)
        db_account.password = hashed_password

    # อัปเดตฟิลด์ต่างๆ ใน account
    if user.email:
        db_account.email = user.email
    if user.name:
        db_account.name = user.name
    if user.phone:
        db_account.phone = user.phone
    if user.is_active is not None:
        db_account.is_active = user.is_active
        
    # อัปเดตฟิลด์ต่างๆ ใน user
    if user.role_id:
        db_user.role_id = user.role_id
    if user.position_id:
        db_user.position_id = user.position_id
    
    db_account.updated_at = datetime.utcnow()
    db_user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_user)
    return db_user

# ฟังก์ชันลบ User ด้วย ID
def delete_user(db: Session, user_id: int):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        return None
        
    # ดึง Account ที่เชื่อมโยงกับ User
    db_account = db.query(Account).filter(Account.id == db_user.account_id).first()
    
    # ลบ User ก่อน
    db.delete(db_user)
    
    # แล้วจึงลบ Account
    if db_account:
        db.delete(db_account)
        
    db.commit()
    return db_user

# อนุญาติให้ผู้ใช้เข้าถึงระบบ
def update_user_status(db: Session, user_id: int, is_active: bool):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        return None
        
    # ดึง Account ที่เชื่อมโยงกับ User
    db_account = db.query(Account).filter(Account.id == db_user.account_id).first()
    if not db_account:
        return None
        
    db_account.is_active = is_active
    db_account.updated_at = datetime.utcnow()
    db_user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_user)
    return db_user

# ดึงข้อมูลผู้ใช้ตามบทบาท
def get_users_by_role(db: Session, role_id: int):
    return db.query(User)\
             .join(Account, Account.id == User.account_id)\
             .filter(User.role_id == role_id, Account.is_active == True)\
             .all()