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
from app.config import settings
from typing import Optional

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
def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=1)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# ฟังก์ชันตรวจสอบ JWT Token
def verify_token(token: str):
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

  

# ฟังก์ชันสำหรับดึงผู้ใช้ปัจจุบันจาก token
# def get_current_user(
#     token: Optional[str] = Cookie(None),
#     authorization: Optional[str] = Header(None),
#     db: Session = Depends(get_db)
# ):
#     print(f"🍪 Token from Cookie: {token}")
#     print(f"🔑 Token from Header: {authorization}")

#     # ตรวจสอบ Token จาก Header ก่อน ถ้าไม่มีให้ตรวจสอบจาก Cookie
    
#     if authorization:
#         token = authorization.replace("Bearer ", "").strip('"')
#     elif token:
#         token = token.replace("Bearer ", "").strip('"')
#     else:
#         print(f"🔑 Token is missing")
#         return None
    
#     try:
#         print(f"🛡️ Final Token: {token}")
#         payload = verify_token(token)
#         email = payload.get("sub")
#         print(f"📧 User Email from Token: {email}")
        
#         if email is None:
#             raise HTTPException(status_code=401, detail="Invalid token payload")
        
#         user = db.query(User).filter(User.email == email).first()
#         if user is None:
#             raise HTTPException(status_code=401, detail="User not found")
        
#         print(f"✅ Authenticated User: {user.email}")
#         return user

#     except jwt.ExpiredSignatureError:
#         print("❌ Token has expired")
#         raise HTTPException(status_code=401, detail="Token has expired")
#     except jwt.InvalidTokenError:
#         print("❌ Invalid Token")
#         raise HTTPException(status_code=401, detail="Invalid token")

# def get_current_user(
#     token: Optional[str] = Cookie(None),
#     authorization: Optional[str] = Header(None),
#     db: Session = Depends(get_db)
# ):
#     print(f"🍪 Token from Cookie: {token}")
#     print(f"🔑 Token from Header: {authorization}")

#     final_token = None
    
#     # ตรวจสอบ Token จาก Header ก่อน
#     if authorization and authorization.startswith("Bearer "):
#         final_token = authorization.replace("Bearer ", "").strip('"')
#     elif token and token.startswith("Bearer "):
#         final_token = token.replace("Bearer ", "").strip('"')
#     else:
#         print("🔑 Token is missing")
#         return None

#     try:
#         print(f"🛡️ Final Token: {final_token}")
#         payload = jwt.decode(final_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
#         email = payload.get("sub")
#         print(f"📧 User Email from Token: {email}")

#         if email is None:
#             raise HTTPException(status_code=401, detail="Invalid token payload")
        
#         user = db.query(User).filter(User.email == email).first()
#         if user is None:
#             raise HTTPException(status_code=401, detail="User not found")
        
#         print(f"✅ Authenticated User: {user.email}")
#         return user

#     except jwt.ExpiredSignatureError:
#         print("❌ Token has expired")
#         raise HTTPException(status_code=401, detail="Token has expired")
#     except jwt.InvalidTokenError as e:
#         print(f"❌ Invalid Token: {str(e)}")
#         raise HTTPException(status_code=401, detail="Invalid token")

# def get_current_user(
#     token: str = Depends(oauth2_scheme),
#     authorization: Optional[str] = Cookie(None),  # เปลี่ยนเป็น Authorization
#     db: Session = Depends(get_db)
# ):
#     payload = verify_token(token)
#     email = payload.get("sub")
    
#     if email is None:
#         raise HTTPException(status_code=401, detail="Invalid token payload")
    
#     user = db.query(User).filter(User.email == email).first()
#     if user is None:
#         raise HTTPException(status_code=401, detail="User not found")
    
    
#     print(f"🔑 Token from Header: {token}")
#     print(f"🍪 Token from Cookie: {authorization}")

#     if not authorization and not token:
#         raise HTTPException(status_code=401, detail="Token is missing from Cookie")

#     try:
#         if authorization:
#         # ตรวจสอบและลบ "Bearer" ออก
#             if authorization.startswith("Bearer "):
#                 token = authorization.replace("Bearer ", "").strip('"')
#             else:
#                 raise HTTPException(status_code=401, detail="Invalid token format in Cookie")

#             print(f"🛡️ Final Token: {token}")
#             payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
#             email = payload.get("sub")
#             print(f"📧 User Email from Token: {email}")

#             if email is None:
#                 raise HTTPException(status_code=401, detail="Invalid token payload")
            
#             user = db.query(User).filter(User.email == email).first()
#             if user is None:
#                 raise HTTPException(status_code=401, detail="User not found")
            
#             print(f"✅ Authenticated User: {user.email}")
#             return user
        
#         else:
#             return None

#     except jwt.ExpiredSignatureError:
#         print("❌ Token has expired")
#         raise HTTPException(status_code=401, detail="Token has expired")
#     except jwt.InvalidTokenError as e:
#         print(f"❌ Invalid Token: {str(e)}")
#         raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(request: Request, db: Session = Depends(get_db)):
    # ✅ ดึง Token จาก Cookie หรือ Header
    token = request.cookies.get("Authorization") or request.headers.get("Authorization")
    if not token:
        return None

    print(f"🔑 Raw Token from get_current_user: {token}")

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

        # ✅ ดึง User จากฐานข้อมูล
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

        print(f"✅ Authenticated User: {user.email}")
        return user  # ✅ คืนค่าเป็น Object ของ User

    except jwt.ExpiredSignatureError:
        print("❌ Token has expired")
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        print(f"❌ Invalid Token: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")





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

# ฟังก์ชันสำหรับตรวจสอบบทบาท ตำแหน่ง และสถานะการใช้งานของผู้ใช้
def get_user_with_role_and_position_and_isActive(required_role: str, required_position: str):
    def role_position_and_active_checker(current_user: User = Depends(get_current_user),request: Request = None):
        if not current_user:
            raise HTTPException(
                status_code=401,
                detail="User authentication failed"
            )

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
        if not current_user.is_active:
            raise HTTPException(
                status_code=403,
                detail="Permission denied: User is not active"
            )
        return current_user
    return role_position_and_active_checker
