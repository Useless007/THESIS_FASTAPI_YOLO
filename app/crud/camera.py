from sqlalchemy.orm import Session
from app.models.camera import Camera
from app.schemas.camera import CameraCreate, CameraUpdate

def get_camera(db: Session, camera_id: int):
    return db.query(Camera).filter(Camera.id == camera_id).first()

def get_cameras(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Camera).offset(skip).limit(limit).all()

def get_camera_by_table(db: Session, table_number: int):
    return db.query(Camera).filter(Camera.table_number == table_number).first()

def create_camera(db: Session, camera: CameraCreate):
    # ตรวจสอบว่าหมายเลขโต๊ะนี้มีการใช้งานแล้วหรือยัง
    existing_camera = get_camera_by_table(db, camera.table_number)
    if existing_camera:
        return None

    # เปลี่ยนจากการใช้ model_dump() (ของ Pydantic v2) เป็น dict() สำหรับ Pydantic v1
    camera_data = camera.dict()
    db_camera = Camera(**camera_data)
    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)
    return db_camera

def update_camera(db: Session, camera_id: int, camera: CameraUpdate):
    db_camera = get_camera(db, camera_id)
    if not db_camera:
        return None

    # ถ้ากำลังอัปเดตหมายเลขโต๊ะ ให้ตรวจสอบด้วยว่าหมายเลขใหม่ยังว่างอยู่หรือเปล่า
    if camera.table_number is not None and camera.table_number != db_camera.table_number:
        existing_camera = get_camera_by_table(db, camera.table_number)
        if existing_camera:
            return None

    # เปลี่ยนจาก model_dump(exclude_unset=True) เป็น dict(exclude_unset=True)
    update_data = camera.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_camera, key, value)
    db.commit()
    db.refresh(db_camera)
    return db_camera

def delete_camera(db: Session, camera_id: int):
    db_camera = get_camera(db, camera_id)
    if db_camera:
        db.delete(db_camera)
        db.commit()
        return True
    return False
