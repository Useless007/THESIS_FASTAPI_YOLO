from fastapi import FastAPI
from app.routers import customer  # นำเข้า router จาก customer.py

app = FastAPI()

# รวม router สำหรับ customer
app.include_router(customer.router)
