# app/services/auth.py

import bcrypt
import jwt
from datetime import datetime, timedelta
from jwt import PyJWTError as JWTError
from sqlalchemy.orm import Session
from fastapi import HTTPException, Depends, Cookie, Header, Request
from fastapi.security import OAuth2PasswordBearer
from app.database import get_db
from app.models.user import User
from app.models.customer import Customer
from app.models.account import Account
from app.config import settings
from typing import Optional, Union, Dict, Any

# กำหนด OAuth2 scheme เพื่อใช้ในการดึง token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/getToken")

# ฟังก์ชันสำหรับแฮชรหัสผ่าน
def hash_password(password: str) -> str:
    # ใช้ bcrypt ในการแฮชรหัสผ่าน
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

# ฟังก์ชันสำหรับตรวจสอบรหัสผ่าน
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# ฟังก์ชันสร้าง JWT Token
def create_access_token(data: dict, is_customer: bool = False, expires_delta: timedelta = timedelta(hours=1)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire, "is_customer": is_customer})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# ฟังก์ชันตรวจสอบ JWT Token
def verify_token(token: str) -> Dict[str, Any]:
    try:
        print("🔍 Raw Token:", token)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=settings.ALGORITHM)
        print("✅ Token Payload:", payload)
        return payload
    except jwt.ExpiredSignatureError:
        print("❌ Token has expired")
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        print("❌ Invalid Token")
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_actor(request: Request, db: Session = Depends(get_db)):
    """
    Get current authenticated user or customer based on the token.
    Return either a User or Customer object, or None if not authenticated.
    """
    # ✅ ดึง Token จาก Cookie หรือ Header
    token = request.cookies.get("Authorization") or request.headers.get("Authorization")
    if not token:
        return None

    print(f"🔑 Raw Token: {token}")

    try:
        # ✅ ลบ "Bearer " และ " หรือช่องว่างที่ไม่ต้องการ
        token = token.replace("Bearer ", "").strip().strip('"')

        # ✅ ตรวจสอบว่ามีค่า Token หรือไม่หลังประมวลผล
        if not token:
            raise HTTPException(status_code=401, detail="Token is empty after processing")

        print(f"🛡️ Processed Token: {token}")

        # ✅ ถอดรหัส JWT Token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        # ✅ ดึง Email จาก Token
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token payload: 'sub' not found")
            
        # ✅ ตรวจสอบว่าเป็น Customer หรือ User
        is_customer = payload.get("is_customer", False)
        
        # ✅ ดึง Account จากฐานข้อมูลด้วย email
        account = db.query(Account).filter(Account.email == email).first()
        if account is None:
            raise HTTPException(status_code=401, detail="Account not found")
            
        if is_customer:
            # ✅ ดึง Customer จากฐานข้อมูล
            actor = db.query(Customer).filter(Customer.account_id == account.id).first()
            if actor is None:
                raise HTTPException(status_code=401, detail="Customer not found")
        else:
            # ✅ ดึง User (Employee) จากฐานข้อมูล
            actor = db.query(User).filter(User.account_id == account.id).first()
            if actor is None:
                raise HTTPException(status_code=401, detail="User not found")
            
        print(f"✅ Authenticated {'Customer' if is_customer else 'User'}: {account.email}")
        return actor

    except jwt.ExpiredSignatureError:
        print("❌ Token has expired")
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        print(f"❌ Invalid Token: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

def get_current_user_or_customer(request: Request, db: Session = Depends(get_db)):
    """
    Get current authenticated user OR customer based on the token.
    Return either a User or Customer object, or None if not authenticated.
    Used for public pages that allow both types of users.
    """
    try:
        return get_current_actor(request, db)
    except HTTPException:
        return None

def get_current_user(request: Request, db: Session = Depends(get_db)):
    """
    Get current authenticated user (employee) based on the token.
    Return a User object or raise HTTPException if not authenticated or is a customer.
    """
    actor = get_current_actor(request, db)
    
    if actor is None:
        return None
    
    # Check if the actor is a User (Employee) and not a Customer
    if isinstance(actor, Customer):
        return None
    
    return actor

def get_current_customer(request: Request, db: Session = Depends(get_db)):
    """
    Get current authenticated customer based on the token.
    Return a Customer object or raise HTTPException if not authenticated or is an employee.
    """
    actor = get_current_actor(request, db)
    
    if actor is None:
        return None
    
    # Check if the actor is a Customer and not a User (Employee)
    if isinstance(actor, User):
        return None
    
    return actor

def get_user_with_role(required_role: int):
    def role_checker(current_user: User = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="User authentication required")
            
        if current_user.role_id != required_role:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: Requires role ID {required_role}"
            )
        return current_user
    return role_checker

def get_user_with_role_and_position(required_role: int, required_position: int):
    def role_and_position_checker(current_user: User = Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=401, detail="User authentication failed")
        
        if current_user.role_id != required_role:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: Requires role ID {required_role}"
            )
        if current_user.position_id != required_position:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: Requires position ID {required_position}"
            )
        return current_user
    return role_and_position_checker

def get_user_with_role_and_position_and_isActive(required_role: int, required_position: int):
    def role_position_and_active_checker(current_user: User = Depends(get_current_user), request: Request = None):
        if not current_user:
            raise HTTPException(
                status_code=401,
                detail="User authentication failed"
            )

        print(f"🔑 Current User: {current_user}")

        if current_user.role_id != required_role:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: Requires role ID {required_role}"
            )

        if current_user.position_id != required_position:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: Requires position ID {required_position}"
            )
        if not current_user.is_active:
            raise HTTPException(
                status_code=403,
                detail="Permission denied: User is not active"
            )
        return current_user
    return role_position_and_active_checker

def authenticate_account(email: str, password: str, db: Session):
    """
    Authenticate a user or customer using email and password.
    Returns (account, is_customer) if successful, or None if authentication fails.
    """
    # ดึงข้อมูล Account จาก email
    account = db.query(Account).filter(Account.email == email).first()
    if not account or not account.is_active:
        return None, False
        
    # ตรวจสอบรหัสผ่าน
    if not verify_password(password, account.password):
        return None, False
        
    # ตรวจสอบว่าเป็น Customer หรือ User
    customer = db.query(Customer).filter(Customer.account_id == account.id).first()
    if customer:
        return account, True
        
    user = db.query(User).filter(User.account_id == account.id).first()
    if user:
        return account, False
        
    return None, False