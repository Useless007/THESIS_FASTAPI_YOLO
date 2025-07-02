# -*- coding: utf-8 -*-
import pymysql
import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from app.database import Base, engine, SessionLocal
from app.models.account import Account
from app.models.address import Address
from app.models.camera import Camera
from app.models.customer import Customer
from app.models.order_item import OrderItem
from app.models.order_status_log import OrderStatusLog
from app.models.order import Order
from app.models.position import Position
from app.models.product import Product
from app.models.role import Role
from app.models.user import User
from app.services.auth import hash_password

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

def init_db():
    db = SessionLocal()
    
    try:
        # ✅ เพิ่มข้อมูล Roles
        roles_data = [
            {"role_id": 1, "role_name": "employee"},
            {"role_id": 2, "role_name": "customer"}
        ]
        
        for role_data in roles_data:
            role = db.query(Role).filter(Role.role_id == role_data["role_id"]).first()
            if not role:
                role = Role(**role_data)
                db.add(role)
                print(f"➕ เพิ่ม Role: {role_data['role_name']}")
        
        db.commit()
        
        # ✅ เพิ่มข้อมูล Positions
        positions_data = [
            {"position_id": 1, "position_name": "executive"},
            {"position_id": 2, "position_name": "admin"},
            {"position_id": 3, "position_name": "preparation"},
            {"position_id": 4, "position_name": "packing"}
        ]
        
        for position_data in positions_data:
            position = db.query(Position).filter(Position.position_id == position_data["position_id"]).first()
            if not position:
                position = Position(**position_data)
                db.add(position)
                print(f"➕ เพิ่ม Position: {position_data['position_name']}")
        
        db.commit()

        # ✅ เพิ่มข้อมูลสินค้า (Products)
        products_data = [
            {
                "product_id": 1, 
                "name": "Arduino Mega 2560", 
                "price": 2305, 
                "description": "Arduino Mega 2560 เป็นบอร์ดที่มีขาสำหรับต่อใช้งานเยอะ จึงเป็นบอร์ดที่นิยมใช้กับโปรเจคที่ต้องการใช้งาน Sensor จำนวนมาก ✅ AI_TRAINED", 
                "image_path": "https://gh.lnwfile.com/_webp_resize_images/600/600/y2/t2/v3.webp",
                "stock": 50
            },
            {
                "product_id": 2, 
                "name": "Arduino UNO WiFi Rev2", 
                "price": 2585, 
                "description": "เริ่มต้นใช้งาน IoT ได้ง่ายด้วย Arduino UNO WiFi Rev.2: จุดเริ่มต้นที่สมบูรณ์แบบสำหรับแอปพลิเคชัน IoT พื้นฐาน มาพร้อมกับดีไซน์แบบ UNO ที่คุ้นเคย ✅ AI_TRAINED", 
                "image_path": "https://inwfile.com/s-o/hhcqzf.png",
                "stock": 50
            },
            {
                "product_id": 3, 
                "name": "Raspberry Pi Compute Module 4 IO Board", 
                "price": 2100, 
                "description": "Compute Module 4 IO Board เป็นแพลตฟอร์มสำหรับการพัฒนาและบอร์ดต้นแบบสำหรับ Compute Module ที่ทรงพลังที่สุดของเรา ✅ AI_TRAINED", 
                "image_path": "https://m.media-amazon.com/images/I/61mjQmDeAGL.jpg",
                "stock": 50
            },
            {
                "product_id": 4, 
                "name": "Raspberry Pi 4 Power Supply", 
                "price": 400, 
                "description": "แหล่งจ่ายไฟคุณภาพสูงที่เชื่อถือได้ ให้กำลังไฟเอาต์พุต 5.1V / 3.0A DC ผ่านช่องต่อ USB-C รองรับการใช้งานกับ Raspberry Pi 4 หรือ 400 ได้อย่างเต็มประสิทธิภาพ ✅ AI_TRAINED", 
                "image_path": "https://media.rs-online.com/R1873418-01.jpg",
                "stock": 50
            },
            {
                "product_id": 5, 
                "name": "SparkFun RedBoard", 
                "price": 965, 
                "description": "SparkFun RedBoard ผสมผสานความเรียบง่ายของ bootloader Optiboot ของ UNO, ความเสถียรของ FTDI และความเข้ากันได้กับ shield ของ Arduino R3 ✅ AI_TRAINED", 
                "image_path": "https://th.mouser.com/images/marketingid/2016/img/141198163_SparkFun_RedBoard.png?v=070223.0225",
                "stock": 50
            },
            {
                "product_id": 6, 
                "name": "Raspberry Pi 7\" Touchscreen Display", 
                "price": 3450, 
                "description": "จอมอนิเตอร์สัมผัสขนาด 7 นิ้วสำหรับ Raspberry Pi ช่วยให้ผู้ใช้สามารถสร้างโปรเจกต์แบบรวมทุกอย่าง ✅ AI_TRAINED", 
                "image_path": "https://i.ebayimg.com/images/g/d1UAAOSwqIdgce3T/s-l1600.jpg",
                "stock": 50
            },
            {
                "product_id": 7, 
                "name": "BeagleBone Black Rev C", 
                "price": 3520, 
                "description": "บซื้อบอร์ดไมโครคอนโทรลเลอร์ BeagleBone Black Rev C แบบไร้สายออนไลน์ มาพร้อมกับโปรเซสเซอร์ 1 GHz AM335x ARM Cortex-A8, หน่วยความจำแฟลช 4 GB, พอร์ต Ethernet และฟีเจอร์อื่น ๆ อีกมากมาย ✅ AI_TRAINED", 
                "image_path": "https://fp.lnwfile.com/_webp_max_images/1024/1024/il/xv/01.webp",
                "stock": 50
            },
            {
                "product_id": 8, 
                "name": "Arduino Uno R3", 
                "price": 290, 
                "description": "Arduino Uno เป็นบอร์ดไมโครคอนโทรลเลอร์ที่ใช้ ATmega328P ในการทำงาน และเป็นบอร์ดยอดนิยมสำหรับผู้เริ่มต้นในการพัฒนาโปรเจกต์ต่าง ๆ ด้วย Arduino มีขนาดเล็ก ราคาไม่สูง และมีความยืดหยุ่นสูง ✅ AI_TRAINED", 
                "image_path": "https://inwfile.com/s-o/v5cjpv.jpg",
                "stock": 50
            },
            {
                "product_id": 9, 
                "name": "Thunderboard EFM32GG12", 
                "price": 1345.19, 
                "description": "Silicon Labs Thunderboard GG12 เป็นจุดเริ่มต้นที่ยอดเยี่ยมในการประเมินผลและพัฒนาแอปพลิเคชันอย่างรวดเร็วด้วย EFM32 Giant Gecko 12 MCU ✅ AI_TRAINED", 
                "image_path": "https://www.mouser.com/images/marketingid/2019/img/199387439.png?v=032924.0305",
                "stock": 50
            },
            {
                "product_id": 10, 
                "name": "MSP432 P401R LaunchPad Development Kit", 
                "price": 1344.86, 
                "description": "ไมโครคอนโทรลเลอร์ MSP430™ จาก Texas Instruments แบบประหยัดพลังงานต่ำพิเศษ สำหรับการตรวจจับและการวัดในแอปพลิเคชันอุตสาหกรรม ✅ AI_TRAINED", 
                "image_path": "https://inex.co.th/home/wp-content/uploads/2020/07/launchpad-msp4322.jpg",
                "stock": 50
            },
            {
                "product_id": 11, 
                "name": "RPI NOIR Camera V2", 
                "price": 404.73, 
                "description": "โมดูลกล้อง 2 Pi NoIR มาพร้อมกับเซ็นเซอร์ Sony IMX219 ความละเอียด 8 เมกะพิกเซล (เมื่อเทียบกับเซ็นเซอร์ OmniVision OV5647 ความละเอียด 5 เมกะพิกเซลของกล้องตัวเดิม) ✅ AI_TRAINED", 
                "image_path": "https://images.prismic.io/rpf-products/72f278a6-5fdd-4ace-87ac-42d4c670b713_Camera+NoIR+Hero.jpg?auto=compress%2Cformat&fit=max",
                "stock": 50
            },
            {
                "product_id": 12, 
                "name": "Power Profik Kit II", 
                "price": 3998.47, 
                "description": "Power Profiler Kit II (PPK2) เป็นอุปกรณ์ที่สามารถวัดกระแสไฟฟ้าของฮาร์ดแวร์ภายนอกและ Nordic DK ทุกชนิด ตั้งแต่กระแสไฟฟ้าต่ำสุดที่ uA ไปจนถึงสูงสุดที่ 1A พร้อมทั้งสามารถเลือกให้ PPK2 จ่ายไฟให้กับอุปกรณ์ได้ โดยเชื่อมต่อผ่านสาย USB 5V มาตรฐาน ✅ AI_TRAINED", 
                "image_path": "https://nl.mouser.com/images/marketingid/2020/img/103756347.png?v=102424.1104",
                "stock": 50
            },
            {
                "product_id": 13, 
                "name": "Raspberry Pi 5 - 8GB RAM", 
                "price": 3257.37, 
                "description": "สิ่งที่ต้องมีเพื่อเริ่มต้นใช้งาน Raspberry Pi 5? 1. ตัวบอร์ด Raspberry Pi 5 : Raspberry Pi 5 8GB RAM, เหมาะสำหรับแอปพลิเคชันที่ต้องการหน่วยความจำขนาดใหญ่ (RAM) เช่น การสร้างสื่อ, เว็บ ✅ AI_TRAINED", 
                "image_path": "https://th.element14.com/productimages/large/en_GB/4256000-40.jpg",
                "stock": 50
            },
            {
                "product_id": 14, 
                "name": "Arducam", 
                "price": 1809.95, 
                "description": "โมดูลกล้องออโต้โฟกัสความละเอียดสูงพิเศษ 64 เมกะพิกเซล ออกแบบมาสำหรับ Raspberry Pi รุ่นล่าสุดและรุ่นอนาคตโดยเฉพาะ โดยใช้เซ็นเซอร์ ✅ AI_TRAINED", 
                "image_path": "https://ae-pic-a1.aliexpress-media.com/kf/S8c91beba8dd24d2296dd62580bcf8609J.jpg_960x960q75.jpg_.avif",
                "stock": 50
            },
            {
                "product_id": 15, 
                "name": "Raspberry Pi AI Kit", 
                "price": 2950, 
                "description": "ชุด Raspberry Pi AI Kit ประกอบด้วย Raspberry Pi M.2 HAT+ พร้อมโมดูลเร่งความเร็ว AI ของ Hailo สำหรับใช้งานร่วมกับ Raspberry Pi 5 ✅ AI_TRAINED", 
                "image_path": "https://i.pcmag.com/imagery/articles/040BL0KDNn510hcKvmB2zzy-2..v1718918612.jpg",
                "stock": 50
            },
            {
                "product_id": 16, 
                "name": "Raspberry Pi Active Cooler", 
                "price": 168.65, 
                "description": "โซลูชันระบายความร้อนแบบหนีบที่ออกแบบมาสำหรับ Raspberry Pi 5 โดยเฉพาะ ประกอบด้วยฮีตซิงก์อะลูมิเนียมและพัดลมเป่าที่ควบคุมอุณหภูมิ ✅ AI_TRAINED", 
                "image_path": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQeBfQVSRjHNGOS8SXJiwbDKxXJrxY3n3X2lw&s",
                "stock": 50
            },
            {
                "product_id": 17, 
                "name": "Arducam ABS Case for IMX... 25° 24mm Camera Boards", 
                "price": 100, 
                "description": "เคสสำหรับกล้องที่ออกแบบมาสำหรับบอร์ดขนาด 25×24 มม., โมดูลกล้อง v1/v2 และโมดูลกล้องอย่างเป็นทางการ V3 (Standard, Wide, NoIR และ NoIR Wide) ✅ AI_TRAINED", 
                "image_path": "https://thepihut.com/cdn/shop/products/arducam-camera-case-arducam-u6251-34471097630915_1000x.jpg?v=1648811700",
                "stock": 50
            }
        ]
        
        for product_data in products_data:
            # ตรวจสอบว่ามีสินค้านี้อยู่แล้วหรือไม่
            product = db.query(Product).filter(Product.product_id == product_data["product_id"]).first()
            if not product:
                product = Product(**product_data)
                db.add(product)
                print(f"➕ เพิ่มสินค้า: {product_data['name']}")
        
        db.commit()
        
        # ✅ สร้าง account และผู้ใช้งานสำหรับพนักงาน
        employees_data = [
            {
                "email": "executive@example.com",
                "password": "executive1234",
                "name": "ทักษ์ดนัย สุวรรณพันธ์",
                "phone": "0891234571",
                "position_id": 1,  # executive
                "is_active": True,
                "address": {
                    "house_number": "99/2",
                    "village_no": "3",
                    "subdistrict": "หนองป่าครั่ง",
                    "district": "เมือง",
                    "province": "เชียงใหม่",
                    "postal_code": "50000"
                }
            },
            {
                "email": "admin@example.com",
                "password": "admin1234",
                "name": "สมพงษ์ รุ่งเรืองวิทย์",
                "phone": "0891234568",
                "position_id": 2,  # admin
                "is_active": True,
                "address": {
                    "house_number": "45/18",
                    "village_no": "7",
                    "subdistrict": "สุเทพ",
                    "district": "เมือง",
                    "province": "เชียงใหม่",
                    "postal_code": "50200"
                }
            },
            {
                "email": "preparation@example.com",
                "password": "preparation1234",
                "name": "วิภาวดี จันทร์เพ็ญ",
                "phone": "0891234588",
                "position_id": 3,  # preparation
                "is_active": True,
                "address": {
                    "house_number": "125/8",
                    "village_no": "4",
                    "subdistrict": "ช้างคลาน",
                    "district": "เมือง",
                    "province": "เชียงใหม่",
                    "postal_code": "50100"
                }
            },
            {
                "email": "packing@example.com",
                "password": "packing1234",
                "name": "ชาญชัย นาคสวัสดิ์",
                "phone": "0891234577",
                "position_id": 4,  # packing
                "is_active": True,
                "address": {
                    "house_number": "222/33",
                    "village_no": "9",
                    "subdistrict": "หายยา",
                    "district": "เมือง",
                    "province": "เชียงใหม่",
                    "postal_code": "50100"
                }
            }
        ]

        for employee_data in employees_data:
            # ตรวจสอบว่ามี account นี้ในฐานข้อมูลแล้วหรือไม่
            account = db.query(Account).filter(Account.email == employee_data["email"]).first()
            
            if not account:
                # สร้าง account ก่อน
                account = Account(
                    email=employee_data["email"],
                    password=hash_password(employee_data["password"]),
                    name=employee_data["name"],
                    phone=employee_data["phone"],
                    is_active=employee_data["is_active"],
                    created_at=datetime.now()
                )
                db.add(account)
                db.flush()  # ให้ flush ก่อนเพื่อให้ได้ ID ที่ถูกต้อง
                
                # สร้าง user ที่เชื่อมโยงกับ account
                user = User(
                    account_id=account.id,
                    role_id=1,  # employee
                    position_id=employee_data["position_id"],
                    created_at=datetime.now()
                )
                db.add(user)
                db.flush()  # ให้ flush เพื่อให้ได้ user.id ก่อนที่จะสร้าง address
                print(f"➕ สร้างบัญชีพนักงาน: {employee_data['name']} ({employee_data['email']}) เรียบร้อยแล้ว")
                
                # เพิ่มที่อยู่ให้กับพนักงาน
                if employee_data["address"]:
                    address = Address(
                        user_id=user.id,  # ใช้ user.id ที่ได้หลังจาก flush
                        customer_id=None,
                        **employee_data["address"]
                    )
                    db.add(address)
                    print(f"➕ เพิ่มที่อยู่ให้กับพนักงาน: {employee_data['email']} เรียบร้อยแล้ว")
                
                db.commit()

        # ✅ สร้างบัญชี customer หลายบัญชี
        customers_data = [
            {
                "email": "customer1@example.com",
                "password": "customer1234",
                "name": "นภัสวรรณ ไชยมงคล",
                "phone": "0891234567",
                "is_active": True,
                "address": {
                    "house_number": "123/45",
                    "village_no": "5",
                    "subdistrict": "สุเทพ",
                    "district": "เมือง",
                    "province": "เชียงใหม่",
                    "postal_code": "50200"
                }
            },
            {
                "email": "customer2@example.com",
                "password": "customer1234",
                "name": "ธีรพงษ์ ศิริวัฒนา",
                "phone": "0891234566",
                "is_active": True,
                "address": {
                    "house_number": "456/78",
                    "village_no": "2",
                    "subdistrict": "ช้างเผือก",
                    "district": "เมือง",
                    "province": "เชียงใหม่",
                    "postal_code": "50300"
                }
            },
            {
                "email": "customer3@example.com",
                "password": "customer1234",
                "name": "สุพรรษา เลิศจิตวาณิชย์",
                "phone": "0891234565",
                "is_active": True,
                "address": None
            },
            {
                "email": "customer4@example.com",
                "password": "customer1234",
                "name": "ปรีชา วงศ์พิพัฒน์",
                "phone": "0891234564",
                "is_active": True,
                "address": {
                    "house_number": "789/10",
                    "village_no": "3",
                    "subdistrict": "หนองหอย",
                    "district": "เมือง",
                    "province": "เชียงใหม่",
                    "postal_code": "50000"
                }
            },
            {
                "email": "customer5@example.com",
                "password": "customer1234",
                "name": "กนกวรรณ ศรีสุวรรณ",
                "phone": "0891234563",
                "is_active": True,
                "address": {
                    "house_number": "101/22",
                    "village_no": "8",
                    "subdistrict": "ป่าตัน",
                    "district": "เมือง",
                    "province": "เชียงใหม่",
                    "postal_code": "50300"
                }
            }
        ]
        
        for customer_data in customers_data:
            # ตรวจสอบว่ามี account นี้ในฐานข้อมูลแล้วหรือไม่
            account = db.query(Account).filter(Account.email == customer_data["email"]).first()
            
            if not account:
                # สร้าง account ก่อน
                account = Account(
                    email=customer_data["email"],
                    password=hash_password(customer_data["password"]),
                    name=customer_data["name"],
                    phone=customer_data["phone"],
                    is_active=customer_data["is_active"],
                    created_at=datetime.now()
                )
                db.add(account)
                db.flush()  # ให้ flush ก่อนเพื่อให้ได้ ID ที่ถูกต้อง
                
                # สร้าง customer ที่เชื่อมโยงกับ account
                customer = Customer(
                    account_id=account.id,
                    created_at=datetime.now()
                )
                db.add(customer)
                db.flush()  # ให้ flush ก่อนเพื่อให้ได้ ID ที่ถูกต้อง
                print(f"➕ สร้างบัญชีลูกค้า: {customer_data['name']} ({customer_data['email']}) เรียบร้อยแล้ว")
                
                # เพิ่มที่อยู่ให้กับลูกค้าถ้ามีข้อมูลที่อยู่
                if customer_data["address"]:
                    address = Address(
                        customer_id=customer.id,
                        **customer_data["address"]
                    )
                    db.add(address)
                    print(f"➕ เพิ่มที่อยู่ให้กับลูกค้า: {customer_data['email']} เรียบร้อยแล้ว")
            
                db.commit()
        
        # ✅ เพิ่มข้อมูลกล้อง
        cameras_data = [
            {
                "id": 1,
                "name": "กล้องโต๊ะ1",
                "stream_url": "rtsp://admin:R2teamza99@192.168.0.242:10544/tcp/av0_0",
                "assigned_to": 4  # packing staff
            },
            {
                "id": 2,
                "name": "กล้องโต๊ะ2",
                "stream_url": "rtsp://admin:R2teamza99@192.168.0.241:10544/tcp/av0_0",
                "assigned_to": None
            }
        ]
        
        for camera_data in cameras_data:
            camera = db.query(Camera).filter(Camera.id == camera_data["id"]).first()
            if not camera:
                camera = Camera(**camera_data)
                db.add(camera)
                print(f"➕ เพิ่มกล้อง: {camera_data['name']}")
        
        db.commit()

    except IntegrityError as e:
        db.rollback()
        print(f"❌ เกิดข้อผิดพลาด Integrity Error: {str(e)}")
    except Exception as e:
        db.rollback()
        print(f"❌ เกิดข้อผิดพลาด: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    print(f"✅ Database `{DB_NAME}` and Tables created successfully!")