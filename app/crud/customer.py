# crud/customer.py

import bcrypt
from sqlalchemy.orm import Session
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate

# ฟังก์ชันสำหรับแฮชรหัสผ่าน
def hash_password(password: str) -> str:
    # ใช้ bcrypt ในการแฮชรหัสผ่าน
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

# ฟังก์ชันสำหรับตรวจสอบรหัสผ่าน
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


# ฟังก์ชันสร้าง Customer ใหม่
def create_customer(db: Session, customer: CustomerCreate):
    # แฮชรหัสผ่านก่อนบันทึก
    hash_password = hash_password(customer.password)

    db_customer = Customer(
        username=customer.username,
        email=customer.email,
        password=hash_password,  
        name=customer.name,
        address=customer.address,
        phone=customer.phone,
    )
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer

# ฟังก์ชันดึงข้อมูล Customer ด้วย ID
def get_customer_by_id(db: Session, customer_id: int):
    return db.query(Customer).filter(Customer.id == customer_id).first()

# ฟังก์ชันดึงข้อมูล Customer ด้วย email
def get_customer_by_email(db: Session, email: str):
    return db.query(Customer).filter(Customer.email == email).first()

# ฟังก์ชันดึงข้อมูล Customer ทั้งหมด (หรือใช้สำหรับการค้นหาลูกค้าทั้งหมด)
def get_all_customers(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Customer).offset(skip).limit(limit).all()

# ฟังก์ชันอัปเดตข้อมูล Customer
def update_customer(db: Session, customer_id: int, customer: CustomerUpdate):
    db_customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_customer:
        return None
    
    # แฮชรหัสผ่านก่อนบันทึก
    if customer.password:
        hash_password = hash_password(customer.password)

    # อัปเดตฟิลด์ต่างๆ
    db_customer.username = customer.username or db_customer.username
    db_customer.email = customer.email or db_customer.email
    db_customer.password = hash_password or db_customer.password  
    db_customer.name = customer.name or db_customer.name
    db_customer.address = customer.address or db_customer.address
    db_customer.phone = customer.phone or db_customer.phone
    db.commit()
    db.refresh(db_customer)
    return db_customer

# ฟังก์ชันลบ Customer ด้วย ID
def delete_customer(db: Session, customer_id: int):
    db_customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_customer:
        return None
    db.delete(db_customer)
    db.commit()
    return db_customer
