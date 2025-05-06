# app/crud/customer.py

from sqlalchemy.orm import Session
from app.models.customer import Customer
from app.models.account import Account
from app.models.address import Address
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.services.auth import verify_password, hash_password
from fastapi import HTTPException
from datetime import datetime


def create_customer(db: Session, customer: CustomerCreate):
    """Create a new customer with hashed password"""
    # แฮชรหัสผ่านก่อนบันทึก
    hashed_password = hash_password(customer.password)
    
    # สร้าง Account ก่อน
    db_account = Account(
        email=customer.email,
        password=hashed_password,
        name=customer.name,
        phone=customer.phone,
        created_at=datetime.utcnow(),
        is_active=customer.is_active
    )
    db.add(db_account)
    db.flush()  # ใช้ flush เพื่อให้ได้ id ของ account
    
    # สร้าง Customer ที่เชื่อมโยงกับ Account
    db_customer = Customer(
        account_id=db_account.id,
        created_at=datetime.utcnow()
    )
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer


def get_customer_by_id(db: Session, customer_id: int):
    """Get customer by ID"""
    return db.query(Customer).filter(Customer.id == customer_id).first()


def get_customer_by_email(db: Session, email: str):
    """Get customer by email"""
    return db.query(Customer)\
             .join(Account, Account.id == Customer.account_id)\
             .filter(Account.email == email)\
             .first()


def get_all_customers(db: Session, skip: int = 0, limit: int = 100):
    """Get all customers with pagination"""
    return db.query(Customer).offset(skip).limit(limit).all()


def update_customer(db: Session, customer_id: int, customer: CustomerUpdate):
    """Update an existing customer"""
    db_customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_customer:
        return None
        
    # ดึง Account ที่เชื่อมโยงกับ Customer
    db_account = db.query(Account).filter(Account.id == db_customer.account_id).first()
    if not db_account:
        return None

    # แฮชรหัสผ่านหากมีการอัปเดต
    if customer.password:
        hashed_password = hash_password(customer.password)
        db_account.password = hashed_password

    # อัปเดตฟิลด์ต่างๆ ใน account
    if customer.email:
        db_account.email = customer.email
    if customer.name:
        db_account.name = customer.name
    if customer.phone:
        db_account.phone = customer.phone
    if customer.is_active is not None:
        db_account.is_active = customer.is_active
    
    db_account.updated_at = datetime.utcnow()
    db_customer.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_customer)
    return db_customer


def delete_customer(db: Session, customer_id: int):
    """Delete customer by ID"""
    db_customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_customer:
        return None
        
    # ดึง Account ที่เชื่อมโยงกับ Customer
    db_account = db.query(Account).filter(Account.id == db_customer.account_id).first()
    
    # ลบ Customer ก่อน
    db.delete(db_customer)
    
    # แล้วจึงลบ Account
    if db_account:
        db.delete(db_account)
        
    db.commit()
    return db_customer


def update_customer_status(db: Session, customer_id: int, is_active: bool):
    """Update customer's active status"""
    db_customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_customer:
        return None
        
    # ดึง Account ที่เชื่อมโยงกับ Customer
    db_account = db.query(Account).filter(Account.id == db_customer.account_id).first()
    if not db_account:
        return None
        
    db_account.is_active = is_active
    db_account.updated_at = datetime.utcnow()
    db_customer.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_customer)
    return db_customer


def add_customer_address(db: Session, customer_id: int, address_data: dict):
    """Add a new address to a customer"""
    db_customer = get_customer_by_id(db, customer_id)
    if not db_customer:
        return None
        
    db_address = Address(
        customer_id=customer_id,
        house_number=address_data.get("house_number"),
        village_no=address_data.get("village_no"),
        subdistrict=address_data.get("subdistrict"),
        district=address_data.get("district"),
        province=address_data.get("province"),
        postal_code=address_data.get("postal_code"),
    )
    
    db.add(db_address)
    db.commit()
    db.refresh(db_address)
    return db_address