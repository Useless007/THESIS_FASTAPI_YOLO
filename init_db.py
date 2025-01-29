# init_db.py

from app.database import Base, engine
# นำเข้าโมเดลทั้งหมดที่ต้องการสร้างตาราง
# from app.models.customer import Customer  
from app.models.product import Product
# from app.models.employee import Employee
from app.models.user import User
from app.models.order import Order

# สร้างตารางทั้งหมดในฐานข้อมูล
Base.metadata.create_all(bind=engine)

print("Tables created successfully!")
