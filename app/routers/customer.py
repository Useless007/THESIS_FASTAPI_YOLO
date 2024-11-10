# routers/customer.py จะเป็นไฟล์ที่ใช้สำหรับการเขียน API สำหรับลูกค้า (Customer) โดยใช้ FastAPI

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerOut
from app.crud.customer import create_customer, get_customer_by_id, get_all_customers, update_customer, delete_customer

router = APIRouter(
    prefix="/customers",  # URL prefix สำหรับ customer
    tags=["Customers"],  # ใช้สำหรับการจัดกลุ่มใน OpenAPI documentation
)

# สร้าง Customer ใหม่
@router.post("/", response_model=CustomerOut)
def create_new_customer(customer: CustomerCreate, db: Session = Depends(get_db)):
    db_customer = create_customer(db=db, customer=customer)
    if db_customer:
        return db_customer
    raise HTTPException(status_code=400, detail="Customer creation failed")

# ดึงข้อมูลลูกค้าโดยใช้ ID
@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    db_customer = get_customer_by_id(db=db, customer_id=customer_id)
    if db_customer:
        return db_customer
    raise HTTPException(status_code=404, detail="Customer not found")

# ดึงข้อมูลลูกค้าทั้งหมด
@router.get("/", response_model=List[CustomerOut])
def get_customers(db: Session = Depends(get_db)):
    return get_all_customers(db=db)

# อัปเดตข้อมูลลูกค้า
@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer_info(customer_id: int, customer: CustomerUpdate, db: Session = Depends(get_db)):
    db_customer = update_customer(db=db, customer_id=customer_id, customer=customer)
    if db_customer:
        return db_customer
    raise HTTPException(status_code=404, detail="Customer not found")

# ลบข้อมูลลูกค้า
@router.delete("/{customer_id}", response_model=CustomerOut)
def delete_customer_info(customer_id: int, db: Session = Depends(get_db)):
    db_customer = delete_customer(db=db, customer_id=customer_id)
    if db_customer:
        return db_customer
    raise HTTPException(status_code=404, detail="Customer not found")
