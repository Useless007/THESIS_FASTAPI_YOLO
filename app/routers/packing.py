# app/routers/packing.py

from concurrent.futures import ThreadPoolExecutor,ProcessPoolExecutor
import asyncio
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException,Query,Header, Response, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.camera import Camera
from app.models.order import Order
from app.services.auth import get_user_with_role_and_position_and_isActive
from app.database import get_db
import subprocess,json,shutil,torch,os,cv2,traceback,threading
from ultralytics import YOLO

router = APIRouter(prefix="/packing", tags=["Packing Staff"])
stream_lock = asyncio.Lock()  # Lock เพื่อจัดการการเข้าถึง Stream

# ✅ โหลดโมเดล YOLOv10
MODEL_PATH = "app/models/best.pt"
UPLOAD_DIR = "uploads/packing_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# stream_lock = threading.Lock()  # Lock เพื่อจัดการการเข้าถึง Stream

try:
    model = YOLO(MODEL_PATH)
except Exception as e:
    raise HTTPException(status_code=500, detail=f"❌ Failed to load YOLOv10 model: {str(e)}")


# ✅ กล้อง IP RTSP
RTSP_LINK = None

# gst_pipeline = (
#     f"rtspsrc location={RTSP_LINK} latency=0 ! "
#     "decodebin ! videoconvert ! appsink"
# )
# video_capture = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)

video_capture = cv2.VideoCapture(RTSP_LINK, cv2.CAP_FFMPEG)
# video_capture = cv2.VideoCapture(RTSP_LINK)
video_capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # ลดขนาด buffer เพื่อประมวลผลได้เร็วขึ้น
video_capture.set(cv2.CAP_PROP_FPS, 15)  # ลด Frame Rate
video_capture.set(cv2.CAP_PROP_POS_MSEC, 5000)  # กำหนด timeout (5 วินาที)

video_captures = {}  # ใช้ camera_id เป็น key

async def start_camera(camera_id: int, rtsp_link: str):
    global video_captures

    # ถ้ามีกล้องตัวนี้อยู่แล้วให้ปิดก่อน
    if camera_id in video_captures:
        video_captures[camera_id].release()
        del video_captures[camera_id]
        await asyncio.sleep(1)

    print(f"🔍 เปิดกล้อง {camera_id} ที่ {rtsp_link}")
    
    video_capture = cv2.VideoCapture(rtsp_link, cv2.CAP_FFMPEG)
    if not video_capture.isOpened():
        print(f"❌ ไม่สามารถเปิดกล้อง {camera_id}")
        return False

    video_captures[camera_id] = video_capture
    print(f"✅ เปิดกล้อง {camera_id} สำเร็จ")
    return True

async def stop_camera(camera_id: int):
    global video_captures
    if camera_id in video_captures:
        print(f"🛑 ปิดกล้อง {camera_id}")
        video_captures[camera_id].release()
        del video_captures[camera_id]
        await asyncio.sleep(1)
    print(f"✅ กล้อง {camera_id} ถูกปิด")

# ✅ แคปภาพจากกล้อง
@router.get("/snapshot")
async def snapshot(
    camera_id: int = Query(..., description="ID ของกล้องที่ต้องการแคปภาพ"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "packing staff"))
):
    global video_captures

    if camera_id not in video_captures or not video_captures[camera_id].isOpened():
        raise HTTPException(status_code=400, detail=f"Camera {camera_id} is not opened")

    success, frame = video_captures[camera_id].read()
    if not success:
        raise HTTPException(status_code=500, detail=f"Cannot read frame from camera {camera_id}")

    # encode เป็น jpg
    _, buffer = cv2.imencode('.jpg', frame)

    return Response(content=buffer.tobytes(), media_type="image/jpeg")



# ✅ สตรีมวิดีโอจากกล้อง
@router.get("/stream")
async def stream_video(
    request: Request,
    camera_id: int = Query(..., description="ID ของกล้องที่ต้องการสตรีม"),
    token: str = Header(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "packing staff"))
):
    global video_captures

    # ดึงข้อมูลกล้องจาก DB
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    rtsp_link = camera.stream_url  # ดึง RTSP link จาก DB

    # ตรวจสอบว่ากล้องถูกเปิดแล้วหรือยัง
    if camera_id not in video_captures or not video_captures[camera_id].isOpened():
        await start_camera(camera_id, rtsp_link)

    # ✅ ฟังก์ชันสร้าง Stream
    async def generate():
        try:
            while True:
                if camera_id not in video_captures or not video_captures[camera_id].isOpened():
                    print(f"⚠️ กล้อง {camera_id} ถูกปิด")
                    break
                success, frame = video_captures[camera_id].read()
                if not success:
                    await asyncio.sleep(0.01)
                    continue
                _, buffer = cv2.imencode('.jpg', frame)
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n'
                )
                await asyncio.sleep(0.01)
        except Exception as e:
            print(f"❌ Error streaming camera {camera_id}: {e}")
        finally:
            await stop_camera(camera_id)

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace;boundary=frame")



# ✅ ปิดกล้อง
@router.get("/stop-stream")
async def stop_stream(
    camera_id: int = Query(..., description="ID ของกล้องที่ต้องการปิด"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "packing staff"))
):
    print(f"🔄 คำขอให้ปิดกล้อง {camera_id}")
    
    await stop_camera(camera_id)

    return JSONResponse(content={"message": f"🛑 กล้อง {camera_id} ถูกปิดสำเร็จ"})


# ✅ สร้างและจัดการ Executor
executor = ThreadPoolExecutor(max_workers=4) 

def get_executor():
    global executor
    if executor is None:
        executor = ThreadPoolExecutor(max_workers=4)
    return executor

# ✅ ฟังก์ชันประมวลผล YOLO
def process_yolo(file_path: str):
    """
    ประมวลผล YOLO บนไฟล์ภาพ
    """
    try:
        results = model.predict(source=file_path, conf=0.1, iou=0.45, stream=False, device='cpu')
        detections = []

        for result in results:
            for box in result.boxes.data:
                x1, y1, x2, y2, conf, cls = box.tolist()
                if conf > 0.3:
                    label = model.names[int(cls)]
                    detections.append({
                        "label": label,
                        "confidence": float(conf),
                        "box": [float(x1), float(y1), float(x2), float(y2)],
                    })

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        print(f"✅ YOLO processing completed: {len(detections)} objects detected.")
        return detections
    except Exception as e:
        print(f"❌ Error in YOLO processing: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing YOLO predictions")



# ✅ Route: ตรวจจับสินค้าในภาพอัปโหลด
@router.post("/detect", response_class=JSONResponse)
async def detect_objects(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "packing staff"))
):
    """
    ตรวจจับวัตถุจากภาพที่อัปโหลดโดยใช้ subprocess เรียก yolo_worker.py
    """  
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    try:
        # ✅ บันทึกไฟล์ภาพ
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if not os.path.exists(file_path):
            raise HTTPException(status_code=400, detail="Uploaded image not found on server.")

        # ✅ เรียกใช้งาน yolo_worker.py ผ่าน subprocess
        result = subprocess.run(
            ["python", "app/services/yolo_worker.py", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Debug logs
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)

        if result.returncode != 0:
            print(f"❌ YOLO worker error: {result.stderr}")
            raise HTTPException(status_code=500, detail="YOLO worker failed.")

        # ✅ ดึงเฉพาะ JSON ที่สมบูรณ์จาก STDOUT
        try:
            start_index = result.stdout.find("{")
            end_index = result.stdout.rfind("}") + 1
            if start_index == -1 or end_index == 0:
                raise json.JSONDecodeError("No JSON found in stdout", result.stdout, 0)
            clean_json = result.stdout[start_index:end_index]
            output = json.loads(clean_json)
        except json.JSONDecodeError:
            print("❌ Failed to decode YOLO worker response.")
            raise HTTPException(status_code=500, detail="Invalid response from YOLO worker.")

        response = JSONResponse(content={"detections": output.get("detections", []), "image_path": file_path})

        # response = JSONResponse(content={"detections": [], "image_path": file_path}) # debug capture only comment out

        return response

    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Unexpected server error during detection process.")


# Endpoint สำหรับดึงรายชื่อกล้อง
@router.get("/cameras", response_class=JSONResponse)
def get_cameras(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "packing staff"))
):
    """
    ดึงรายชื่อกล้องที่เก็บไว้ใน DB
    สมมุติว่า Model Camera มี attribute: id, table_number, name, stream_url
    """
    cameras = db.query(Camera).all()
    return [
        {
            "id": camera.id,
            "table_number": camera.table_number,
            "name": camera.name,
            "stream_url": camera.stream_url
        } for camera in cameras
    ]

# Endpoint สำหรับดึงรายการคำสั่งซื้อที่มีสถานะ packing
@router.get("/orders/packing", response_class=JSONResponse)
def get_packing_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "packing staff"))
):
    """
    ดึงรายการคำสั่งซื้อที่มีสถานะ packing เพื่อนำมาตรวจสอบว่าสินค้ามีหรือไม่
    เฉพาะออเดอร์ที่ยังไม่ถูก assign หรือออเดอร์ที่ถูก assign ให้กับพนักงานปัจจุบัน
    """
    orders = db.query(Order)\
        .filter(or_(Order.assigned_to == None, Order.assigned_to == current_user.id))\
        .filter(Order.status.in_(["packing", "in_progres"]))\
        .all()
    return [
        {
            "id": order.order_id,
            "email": order.email,
            "total": order.total,
            "created_at": order.created_at,
            "items": order.item,
            "assigned_to": order.assigned_to
        } for order in orders
    ]

@router.put("/orders/{order_id}/assign", response_class=JSONResponse)
def assign_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "packing staff"))
):
    order = (
        db.query(Order)
        .filter(
            and_(
                Order.order_id == order_id,
                Order.status == "packing",
                Order.assigned_to == None
            )
        )
        .with_for_update()
        .first()
    )
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or already assigned")

    order.assigned_to = current_user.id
    order.status = "in_progress"
    db.commit()
    db.refresh(order)

    # ✅ แปลง `items` จาก string JSON เป็น list
    try:
        items = json.loads(order.item)
    except json.JSONDecodeError:
        items = []
        print("❌ Error decoding items JSON")

    # ✅ สร้างข้อมูลที่พร้อมใช้ใน Frontend
    formatted_items = [
        {
            "product_id": item.get("product_id", "N/A"),
            "product_name": item.get("name", "Unknown"),
            "quantity": item.get("quantity", 0),
            "price": item.get("price", 0.0),
            "total": item.get("total", 0.0)
        }
        for item in items
    ]

    order_data = {
        "order_id": order.order_id,
        "customer_email": order.email,
        "total_price": order.total,
        "items": formatted_items,  # ✅ ใช้ข้อมูลที่แปลงแล้ว
        "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    }

    return JSONResponse(content=order_data)

