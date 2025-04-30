from sqlalchemy.orm import Session, joinedload
from app.models.camera import Camera
from app.schemas.camera import CameraCreate, CameraUpdate

def get_camera(db: Session, camera_id: int):
    return db.query(Camera).options(joinedload(Camera.assigned_user)).filter(Camera.id == camera_id).first()

def get_cameras(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Camera).options(joinedload(Camera.assigned_user)).offset(skip).limit(limit).all()

def create_camera(db: Session, camera: CameraCreate):
    # ไม่ต้องตรวจสอบ table_number
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