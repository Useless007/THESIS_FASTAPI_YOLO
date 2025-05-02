# app/routers/packing.py

from concurrent.futures import ThreadPoolExecutor,ProcessPoolExecutor
import asyncio
import requests
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException,Query,Header, Response, Request, Form
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload
from app.models.user import User
from app.models.camera import Camera
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.schemas.order import VerifyRequest
from app.services.auth import get_user_with_role_and_position_and_isActive, get_current_user
from app.database import get_db
import subprocess,json,shutil,torch,os,cv2,traceback,threading
from ultralytics import YOLO

router = APIRouter(prefix="/packing", tags=["Packing Staff"])
stream_lock = asyncio.Lock()  # Lock เพื่อจัดการการเข้าถึง Stream

# ✅ โหลดโมเดล YOLOv10
MODEL_PATH = "app/models/best.pt"
ONNX_MODEL_PATH = "app/models/best.onnx"
UPLOAD_DIR = "uploads/packing_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ✅ ตรวจสอบว่า ONNX model มีอยู่จริง
if not os.path.exists(ONNX_MODEL_PATH):
    print(f"⚠️ ONNX model not found at {ONNX_MODEL_PATH}")
else:
    print(f"✅ ONNX model found at {ONNX_MODEL_PATH}")

# stream_lock = threading.Lock()  # Lock เพื่อจัดการการเข้าถึง Stream

try:
    model = YOLO(MODEL_PATH)
except Exception as e:
    raise HTTPException(status_code=500, detail=f"❌ Failed to load YOLOv10 model: {str(e)}")

# ✅ API สำหรับดาวน์โหลด ONNX model ไปใช้ใน frontend
@router.get("/model")
async def get_onnx_model(
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
):
    """
    Return the ONNX model file for frontend real-time detection
    """
    if not os.path.exists(ONNX_MODEL_PATH):
        raise HTTPException(status_code=404, detail="ONNX model not found")
    
    # แก้ไขเพื่อให้ browser แปลความหมายไฟล์ได้ถูกต้อง
    # เปลี่ยน media_type เป็น application/octet-stream
    # และใช้ headers อย่างชัดเจนเพื่อปิดการ transform ข้อมูล
    return FileResponse(
        ONNX_MODEL_PATH, 
        media_type="application/octet-stream",
        filename="best.onnx",
        headers={
            "Content-Disposition": "attachment; filename=best.onnx",
            "Content-Type": "application/octet-stream",
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

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
detection_flags = {}  # ใช้ camera_id เป็น key เพื่อเก็บสถานะว่ากำลังตรวจจับหรือไม่
detection_processes = {}  # เก็บ process ของการตรวจจับ

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
    global video_captures, detection_flags
    if camera_id in video_captures:
        print(f"🛑 ปิดกล้อง {camera_id}")
        video_captures[camera_id].release()
        del video_captures[camera_id]
        # ยกเลิกการตรวจจับด้วย
        if camera_id in detection_flags:
            detection_flags[camera_id] = False
        await asyncio.sleep(1)
    print(f"✅ กล้อง {camera_id} ถูกปิด")

# ฟังก์ชันสำหรับการวาดกรอบและฉลากบนภาพ
def draw_detections(frame, detections):
    for detection in detections:
        label = detection["label"]
        conf = detection["confidence"]
        box = detection["box"]
        
        x1, y1, x2, y2 = [int(coord) for coord in box]
        
        # วาดกรอบ
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # ตำแหน่งของฉลาก
        y = y1 - 15 if y1 - 15 > 15 else y1 + 15
        
        # วาดฉลากและค่าความเชื่อมั่น
        label_text = f"{label}: {conf:.2f}"
        cv2.putText(frame, label_text, (x1, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    return frame

# ✅ แคปภาพจากกล้อง
@router.get("/snapshot")
async def snapshot(
    camera_id: int = Query(..., description="ID ของกล้องที่ต้องการแคปภาพ"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
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
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
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



# ✅ สตรีมวิดีโจากกล้องพร้อมการตรวจจับแบบ real-time
@router.get("/realtime-detect")
async def realtime_detect(
    request: Request,
    camera_id: int = Query(..., description="ID ของกล้องที่ต้องการสตรีมพร้อมตรวจจับ"),
    token: str = Header(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
):
    global video_captures, detection_flags
    
    # ดึงข้อมูลกล้องจาก DB
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    rtsp_link = camera.stream_url  # ดึง RTSP link จาก DB

    # ตรวจสอบว่ากล้องถูกเปิดแล้วหรือยัง
    if camera_id not in video_captures or not video_captures[camera_id].isOpened():
        await start_camera(camera_id, rtsp_link)

    # เตรียม model สำหรับการตรวจจับ
    device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
    print(f"🔍 Running YOLO on device: {device} for camera {camera_id}")
    
    # เริ่มตรวจจับ
    detection_flags[camera_id] = True
    
    # ✅ ฟังก์ชันสร้าง Stream ที่มีการตรวจจับวัตถุ
    async def generate():
        try:
            while detection_flags.get(camera_id, True):
                if camera_id not in video_captures or not video_captures[camera_id].isOpened():
                    print(f"⚠️ กล้อง {camera_id} ถูกปิด")
                    break
                    
                success, frame = video_captures[camera_id].read()
                if not success:
                    await asyncio.sleep(0.1)
                    continue
                
                # ทำการตรวจจับวัตถุด้วย YOLO
                try:
                    # บันทึกภาพชั่วคราว
                    temp_path = f"temp_frame_{camera_id}.jpg"
                    cv2.imwrite(temp_path, frame)
                    
                    # ตรวจสอบว่าไฟล์ถูกบันทึกสำเร็จหรือไม่
                    if not os.path.exists(temp_path):
                        print(f"⚠️ ไม่สามารถบันทึกไฟล์ภาพชั่วคราว {temp_path}")
                        await asyncio.sleep(0.1)
                        continue
                    
                    # ใช้ subprocess เรียก yolo_worker.py เหมือนกับฟังก์ชัน detect_objects
                    try:
                        result = subprocess.run(
                            ["python", "app/services/yolo_worker.py", temp_path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        
                        if result.returncode != 0:
                            print(f"❌ YOLO worker error in real-time: {result.stderr}")
                            continue
                        
                        # Parse JSON output
                        try:
                            start_index = result.stdout.find("{")
                            end_index = result.stdout.rfind("}") + 1
                            if start_index != -1 and end_index > 0:
                                clean_json = result.stdout[start_index:end_index]
                                output = json.loads(clean_json)
                                
                                # ใช้ภาพที่มีการวาดกรอบแล้วจาก yolo_worker
                                annotated_path = output.get("annotated_image")
                                if annotated_path and os.path.exists(annotated_path):
                                    # อ่านภาพที่มีการวาดกรอบแล้ว
                                    frame = cv2.imread(annotated_path)
                                    
                                    # ลบไฟล์ที่มีการวาดกรอบ
                                    try:
                                        os.remove(annotated_path)
                                    except Exception as e:
                                        print(f"⚠️ ไม่สามารถลบไฟล์ที่มีการวาดกรอบ: {e}")
                        except json.JSONDecodeError:
                            print("❌ Failed to decode YOLO worker response in real-time.")
                        
                    except Exception as e:
                        print(f"❌ Error running YOLO worker in real-time: {str(e)}")
                    
                    # ลบไฟล์ชั่วคราว
                    try:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except Exception as e:
                        print(f"⚠️ ไม่สามารถลบไฟล์ชั่วคราว: {str(e)}")
                    
                except Exception as e:
                    print(f"❌ Error in real-time detection: {str(e)}")
                
                # แปลงเป็น JPEG เพื่อส่งไปแสดงผล
                _, buffer = cv2.imencode('.jpg', frame)
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n'
                )
                
                # หน่วงเวลาเพื่อไม่ให้ทำงานหนักเกินไป
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"❌ Error streaming camera with detection {camera_id}: {e}")
        finally:
            # ปิดการตรวจจับแต่ไม่ปิดกล้อง
            detection_flags[camera_id] = False
            # ลบไฟล์ชั่วคราวที่อาจหลงเหลืออยู่
            temp_path = f"temp_frame_{camera_id}.jpg"
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
    
    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace;boundary=frame")

# ✅ หยุดการตรวจจับแบบ real-time
@router.get("/stop-realtime")
async def stop_realtime_detection(
    camera_id: int = Query(..., description="ID ของกล้องที่ต้องการหยุดตรวจจับ"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
):
    global detection_flags
    
    print(f"🔄 คำขอให้หยุดตรวจจับ real-time กล้อง {camera_id}")
    
    # หยุดการตรวจจับแต่ไม่ปิดกล้อง
    detection_flags[camera_id] = False
    
    return JSONResponse(content={"message": f"🛑 หยุดการตรวจจับ real-time กล้อง {camera_id} สำเร็จ"})

# ✅ ปิดกล้อง
@router.get("/stop-stream")
async def stop_stream(
    camera_id: int = Query(..., description="ID ของกล้องที่ต้องการปิด"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
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
        # ตรวจสอบว่าไฟล์มีอยู่จริง
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return []
        
        # ตรวจสอบว่า CUDA (GPU) พร้อมใช้งานหรือไม่
        device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        print(f"🔍 Running YOLO on device: {device}")
        
        # ใช้ file path โดยตรง (อย่าแปลงเป็น OpenCV image)
        results = model.predict(source=file_path, conf=0.1, iou=0.45, stream=False, device=device)
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
        traceback.print_exc()  # เพิ่ม traceback เพื่อดูรายละเอียดข้อผิดพลาด
        return []  # ส่งคืนลิสต์ว่างแทนการ raise exception เพื่อให้โปรแกรมทำงานต่อได้



# ✅ Route: ตรวจจับสินค้าในภาพอัปโหลด
@router.post("/detect", response_class=JSONResponse)
async def detect_objects(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
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

        response = JSONResponse(content={"detections": output.get("detections", []), "image_path": file_path, "annotated_image_path": output.get("annotated_image", "") })

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
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
):
    """
    ดึงรายชื่อกล้องที่เก็บไว้ใน DB
    สมมุติว่า Model Camera มี attribute: id, table_number, name, stream_url
    """
    cameras = db.query(Camera).all()
    return [
        {
            "id": camera.id,
            # "table_number": camera.table_number,
            "name": camera.name,
            "stream_url": camera.stream_url
        } for camera in cameras
    ]

# Endpoint สำหรับดึงรายการคำสั่งซื้อที่มีสถานะ packing
@router.get("/orders/packing", response_class=JSONResponse)
def get_packing_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
):
    """
    ดึงรายการคำสั่งซื้อที่มีสถานะ packing เพื่อนำมาตรวจสอบว่าสินค้ามีหรือไม่
    เฉพาะออเดอร์ที่ยังไม่ถูก assign หรือออเดอร์ที่ถูก assign ให้กับพนักงานปัจจุบัน
    """
    orders = db.query(Order)\
        .options(joinedload(Order.user))\
        .filter(or_(Order.assigned_to == None, Order.assigned_to == current_user.id))\
        .filter(Order.status.in_(["packing", "verifying"]))\
        .all()
    return [
        {
            "id": order.order_id,
            "email": order.user.email if order.user else None,  # เปลี่ยนจาก order.email เป็น order.user.email
            "total": order.total,
            "created_at": order.created_at,
            "items": order.order_items,
            "assigned_to": order.assigned_to
        } for order in orders
    ]

@router.put("/orders/{order_id}/assign", response_class=JSONResponse)
def assign_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
):
    order = (
        db.query(Order)
        .options(
            joinedload(Order.user),
            joinedload(Order.order_items).joinedload(OrderItem.product)
        )
        .filter(
            and_(
                Order.order_id == order_id,
                Order.status.in_(["packing", "pending"]),
                Order.assigned_to == None
            )
        )
        .with_for_update()
        .first()
    )
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or already assigned")

    order.assigned_to = current_user.id
    order.status = "verifying"
    db.commit()
    db.refresh(order)

    # Format the order items properly
    formatted_items = [
        {
            "product_id": item.product_id,
            "product_name": item.product.name if item.product else "Unknown",
            "quantity": item.quantity,
            "price": item.price_at_order,
            "total": item.total_item_price
        }
        for item in order.order_items
    ]

    order_data = {
        "order_id": order.order_id,
        "customer_email": order.user.email if order.user else None,
        "total_price": order.total,
        "items": formatted_items,
        "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    }

    return JSONResponse(content=order_data)

@router.post("/orders/{order_id}/upload-image", response_class=JSONResponse)
async def upload_packed_image(
    order_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
):
    """
    อัปโหลดรูปสินค้าที่แพ็คเสร็จแล้ว และเก็บไว้ในฐานข้อมูล
    """
    order = db.query(Order).filter(Order.order_id == order_id, Order.assigned_to == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not assigned to you")

    upload_dir = "uploads/packed_orders"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{order_id}.jpg")

    # ✅ บันทึกไฟล์
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    order.image_path = file_path  # บันทึก path ไฟล์ลง database
    db.commit()

    return JSONResponse(content={"message": "Image uploaded successfully", "image_path": file_path})

@router.put("/orders/{order_id}/verify", response_class=JSONResponse)
async def verify_order(
    order_id: int,
    verified: bool = Form(...),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
):
    """
    ✅ พนักงานกดยืนยันสินค้าครบหรือไม่ครบ
    """
    order = db.query(Order).filter(Order.order_id == order_id, Order.assigned_to == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not assigned to you")

    if not file and not order.image_path:
        raise HTTPException(status_code=400, detail="กรุณาตรวจจับสินค้าก่อน")

    if file:
        upload_dir = "uploads/packed_orders"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{order_id}.jpg").replace("\\", "/")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        order.image_path = file_path

    # ✅ ถ้าสินค้าไม่ครบ → เปลี่ยนสถานะเป็น "pending" และแจ้งเตือนแอดมิน
    if not verified:
        order.status = "pending"
        db.commit()

        # ✅ ส่ง HTTP Request ไปยัง Home เพื่อให้แจ้งเตือน Admin
        try:
            url = "http://localhost:8000/admin/trigger-notify"
            # url = "https://home.jintaphas.tech/admin/trigger-notify"
            payload = {
                "order_id": order_id,
                "reason": "สินค้าไม่ครบ"
            }
            resp = requests.post(url, json=payload, timeout=5)
            print("Notify admin response:", resp.status_code, resp.text)
        except Exception as e:
            print("Error calling home to notify admin:", e)

        return JSONResponse(content={"message": "Order marked as pending", "order_id": order_id, "status": "pending"})

    # ✅ ถ้าสินค้าครบ → อัปเดตเป็น "completed"
    order.is_verified = verified
    order.status = "completed"
    db.commit()

    return JSONResponse(content={"message": "Order verification updated", "order_id": order_id, "status": "completed"})

@router.get("/orders/current", response_class=JSONResponse)
def get_current_order(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
):
    """
    ✅ ดึงข้อมูลออเดอร์ที่พนักงานกำลังแพ็คอยู่
    """
    order = db.query(Order)\
        .options(
            joinedload(Order.user),
            joinedload(Order.order_items).joinedload(OrderItem.product)
        )\
        .filter(
            Order.assigned_to == current_user.id,  
            Order.status.in_(["verifying", "packing"])
        )\
        .order_by(Order.created_at.desc())\
        .first()

    if not order:
        return JSONResponse(content={"message": "No active order"}, status_code=200)

    formatted_items = [
        {
            "product_id": item.product_id,
            "product_name": item.product.name if item.product else "Unknown",
            "quantity": item.quantity,
            "price": item.price_at_order,
            "total": item.total_item_price
        }
        for item in order.order_items
    ]

    return JSONResponse(content={
        "order_id": order.order_id,
        "customer_email": order.user.email if order.user else None,
        "total_price": order.total,
        "items": formatted_items,
        "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "image_path": order.image_path
    })

@router.get("/orders/{order_id}/image", response_class=FileResponse)
async def get_order_image(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    ✅ ให้ API ส่งรูปภาพสินค้าแพ็คแล้วแทนการเข้าถึงโดยตรง
    """
    order = db.query(Order).filter(Order.order_id == order_id, Order.user_id == current_user.id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or you don't have permission.")

    # ✅ เช็คว่ามีไฟล์ภาพจริงไหม
    if not order.image_path or not os.path.exists(order.image_path):
        raise HTTPException(status_code=404, detail="No packed order image found.")

    return FileResponse(order.image_path, media_type="image/jpeg")

# Add a new endpoint to fetch all product names for the YOLO detector
@router.get("/product-names", response_class=JSONResponse)
def get_product_names(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
):
    """
    ดึงรายชื่อสินค้าทั้งหมดเพื่อใช้กับ YOLO detector
    """
    products = db.query(Product.name).all()
    product_names = [product[0] for product in products]
    
    return JSONResponse(content={"product_names": product_names})