# services/auth.py

import bcrypt
import jwt
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from app.database import get_db
from app.models.user import User
from app.config import settings

# กำหนด OAuth2 scheme เพื่อใช้ในการดึง token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# ฟังก์ชันสำหรับแฮชรหัสผ่าน
def hash_password(password: str) -> str:
    # ใช้ bcrypt ในการแฮชรหัสผ่าน
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

# ฟังก์ชันสำหรับตรวจสอบรหัสผ่าน
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# ฟังก์ชันสร้าง JWT Token
def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=1)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# ฟังก์ชันตรวจสอบ JWT Token
def verify_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=settings.ALGORITHM)
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    

# ฟังก์ชันสำหรับดึงผู้ใช้ปัจจุบันจาก token
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = verify_token(token)  # ใช้ verify_token ในการตรวจสอบ token
    email = payload.get("sub")
    
    if email is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    user = db.query(User).filter(User.email == email).first()
    
    if user is None:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    return user  # คืนค่า user ถ้า authenticated แล้ว


# ฟังก์ชันสำหรับตรวจสอบบทบาทของผู้ใช้
def get_user_with_role(required_role: str):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role != required_role:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: Requires {required_role} role"
            )
        return current_user
    return role_checker

# ฟังก์ชันสำหรับตรวจสอบบทบาทและตำแหน่งของผู้ใช้
def get_user_with_role_and_position(required_role: str, required_position: str):
    def role_and_position_checker(current_user: User = Depends(get_current_user)):
        if current_user.role != required_role:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: Requires {required_role} role"
            )
        if current_user.position != required_position:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: Requires {required_position} position"
            )
        return current_user
    return role_and_position_checker