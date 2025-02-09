import pymysql
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from app.database import Base, engine
from app.models.user import User
from app.models.order import Order
from app.models.camera import Camera

# ✅ โหลดค่าตัวแปรจาก .env
load_dotenv()

DB_USER = os.getenv("DATABASE_USERNAME", "root")
DB_PASSWORD = os.getenv("DATABASE_PASSWORD", "")
DB_HOST = os.getenv("DATABASE_HOST", "localhost")
DB_PORT = os.getenv("DATABASE_PORT", "3306")
DB_NAME = os.getenv("DATABASE_NAME", "17iot_yolo_project")

# ✅ เชื่อมต่อ MySQL และสร้าง database ถ้ายังไม่มี
connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, port=int(DB_PORT))
cursor = connection.cursor()
cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
cursor.close()
connection.close()

# ✅ อัปเดต `engine` ให้เชื่อมต่อกับ database ที่เพิ่งสร้าง
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

# ✅ สร้างตารางทั้งหมดใน database
Base.metadata.create_all(bind=engine)

print(f"✅ Database `{DB_NAME}` and Tables created successfully!")
