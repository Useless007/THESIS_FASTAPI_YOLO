# app/routers/packing.py

from concurrent.futures import ThreadPoolExecutor,ProcessPoolExecutor
import asyncio
import requests
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException,Query,Header, Response, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, HTMLResponse
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
from app.services.ws_manager import notify_admin, notify_preparation
from datetime import datetime
import subprocess,json,shutil,torch,os,cv2,traceback,threading,time,re,base64
import numpy as np
from ultralytics import YOLO
from fastapi.templating import Jinja2Templates

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

# ✅ ฟังก์ชันสำหรับตรวจจับวัตถุบน frame (นำมาจาก yolo_worker.py ซึ่งทำงานได้จริง)
def detect_frame(frame, device='cuda:0'):
    """
    ตรวจจับวัตถุโดยเขียนเฟรมเป็นไฟล์ชั่วคราว และใช้วิธีการเดียวกับ yolo_worker.py
    """
    try:
        # ตรวจสอบว่า frame เป็น numpy array ที่ถูกต้อง
        if frame is None or frame.size == 0:
            print("❌ Invalid frame for detection")
            return []
        
        # สร้าง temp directory ถ้ายังไม่มี
        temp_dir = "uploads/temp_realtime"
        os.makedirs(temp_dir, exist_ok=True)
        
        # สร้างชื่อไฟล์ชั่วคราวที่ไม่ซ้ำกัน
        temp_path = os.path.join(temp_dir, f"temp_frame_{time.time()}.jpg")
        
        # บันทึกภาพลงไฟล์ชั่วคราว
        cv2.imwrite(temp_path, frame)
        
        if not os.path.exists(temp_path):
            print(f"❌ Failed to write temporary file: {temp_path}")
            return []
            
        try:
            # ใช้ subprocess เรียก yolo_worker.py แทนการเรียกใช้โมเดลโดยตรง
            result = subprocess.run(
                ["python", "app/services/yolo_worker.py", temp_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode != 0:
                print(f"❌ YOLO worker error in real-time: {result.stderr}")
                return []
            
            # Parse JSON output
            try:
                start_index = result.stdout.find("{")
                end_index = result.stdout.rfind("}") + 1
                if start_index == -1 or end_index == 0:
                    return []
                clean_json = result.stdout[start_index:end_index]
                output = json.loads(clean_json)
                
                # ใช้ผลลัพธ์การตรวจจับวัตถุจาก YOLO worker
                detections = output.get("detections", [])
                
                return detections
            except json.JSONDecodeError:
                print("❌ Failed to decode YOLO worker response in real-time.")
                return []
                
        finally:
            # ลบไฟล์ชั่วคราวทันทีไม่ว่าจะสำเร็จหรือไม่ก็ตาม
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as e:
                print(f"⚠️ Warning: Failed to delete temporary file: {e}")
    except Exception as e:
        print(f"❌ Error in frame detection: {str(e)}")
        traceback.print_exc()
        return []

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
            # เก็บเฟรมล่าสุดที่ทำการตรวจจับแล้ว
            last_detection_time = 0
            detection_interval = 2.0  # ทำการตรวจจับทุก 2 วินาที (0.5 FPS สำหรับการตรวจจับ)
            
            # กรอบตรวจจับล่าสุด (ใช้วาดบนเฟรมใหม่)
            last_detections = []
            
            # ตั้งค่า device เพื่อใช้ในการตรวจจับ
            device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
            print(f"🔍 Running YOLO on device: {device} for camera {camera_id}")
            
            while detection_flags.get(camera_id, True):
                if camera_id not in video_captures or not video_captures[camera_id].isOpened():
                    print(f"⚠️ กล้อง {camera_id} ถูกปิด")
                    break
                    
                success, frame = video_captures[camera_id].read()
                if not success:
                    await asyncio.sleep(0.01)  # ลดเวลารอเป็น 0.01 วินาที
                    continue
                
                current_time = time.time()
                should_detect = (current_time - last_detection_time) >= detection_interval
                
                if should_detect:
                    last_detection_time = current_time
                    
                    try:
                        # ตรวจสอบความถูกต้องของเฟรม
                        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
                            print(f"⚠️ Invalid frame received from camera {camera_id}")
                            await asyncio.sleep(0.01)
                            continue
                        
                        try:
                            # ทำสำเนาเฟรมก่อนนำไปประมวลผล
                            frame_copy = frame.copy()
                            
                            # กำหนดตัวแปร detections ตั้งแต่ต้นเพื่อแก้ปัญหา "referenced before assignment"
                            detections = []
                            
                            # ใช้ subprocess เรียก yolo_worker.py เพื่อตรวจจับวัตถุ
                            # ซึ่งเป็นวิธีที่ทำงานได้จริงแล้วในฟังก์ชันอื่นๆ
                            # จำเป็นต้องเขียนลงไฟล์ชั่วคราว แต่คุณสามารถลดขนาดรูปภาพลงเพื่อให้เร็วขึ้น
                            
                            # สร้าง temp directory ถ้ายังไม่มี
                            temp_dir = "uploads/temp_realtime"
                            os.makedirs(temp_dir, exist_ok=True)
                            
                            # ลดขนาดเฟรมลงเพื่อให้การเขียนไฟล์และตรวจจับเร็วขึ้น (ลดลงมากขึ้น)
                            frame_resized = cv2.resize(frame_copy, (320, 240))
                            
                            # สร้างชื่อไฟล์ชั่วคราวที่ไม่ซ้ำกัน
                            temp_path = os.path.join(temp_dir, f"temp_frame_{camera_id}_{time.time()}.jpg")
                            
                            # บันทึกภาพลงไฟล์ชั่วคราวด้วยคุณภาพต่ำเพื่อให้เร็วขึ้น
                            cv2.imwrite(temp_path, frame_resized, [cv2.IMWRITE_JPEG_QUALITY, 50])
                            
                            # ใช้ subprocess เรียก yolo_worker.py ซึ่งทำงานได้แล้ว
                            # เพิ่ม timeout เป็น 10 วินาที
                            result = subprocess.run(
                                ["python", "app/services/yolo_worker.py", temp_path],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                timeout=10  # เพิ่ม timeout เป็น 10 วินาที
                            )
                            
                            # ลบไฟล์ชั่วคราวทันที
                            try:
                                if os.path.exists(temp_path):
                                    os.remove(temp_path)
                            except Exception as e:
                                print(f"⚠️ Warning: Failed to delete temporary file: {e}")
                            
                            if result.returncode != 0:
                                print(f"❌ YOLO worker error: {result.stderr}")
                                detections = []
                            else:
                                # แยก JSON จาก stdout
                                try:
                                    start_index = result.stdout.find("{")
                                    end_index = result.stdout.rfind("}") + 1
                                    if start_index == -1 or end_index == 0:
                                        detections = []
                                    else:
                                        clean_json = result.stdout[start_index:end_index]
                                        output = json.loads(clean_json)
                                        detections = output.get("detections", [])
                                except json.JSONDecodeError:
                                    print("❌ Failed to decode YOLO worker response")
                                    detections = []
                                    
                            # วาดกรอบรอบวัตถุที่ตรวจพบ
                            for detection in detections:
                                label = detection["label"]
                                conf = detection["confidence"]
                                box = detection["box"]
                                
                                x1, y1, x2, y2 = [int(float(coord)) for coord in box]
                                
                                # วาดกรอบ
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                
                                # วาดข้อความแสดงชื่อและความเชื่อมั่น
                                label_text = f"{label}: {conf:.2f}"
                                cv2.putText(frame, label_text, (x1, y1 - 10), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
                        except Exception as e:
                            print(f"❌ Error in detection: {str(e)}")
                            traceback.print_exc()
                        
                        # แปลงภาพที่มีการวาดกรอบแล้วเป็น base64
                        _, buffer = cv2.imencode('.jpg', frame)
                        yield (
                            b'--frame\r\n'
                            b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n'
                        )
                        
                    except Exception as e:
                        print(f"❌ Error in detection: {str(e)}")
                        traceback.print_exc()
                
                # รอสักครู่เพื่อไม่ให้ใช้ CPU มากเกินไป
                await asyncio.sleep(0.01)
                
        except Exception as e:
            print(f"❌ Error streaming camera with detection {camera_id}: {e}")
        finally:
            # ปิดการตรวจจับแต่ไม่ปิดกล้อง
            detection_flags[camera_id] = False

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace;boundary=frame")

# ✅ เพิ่ม WebSocket endpoint สำหรับแสดงภาพทั้งต้นฉบับและภาพที่มีการตรวจจับพร้อมกัน
@router.websocket("/ws/dual-stream")
async def dual_stream_ws(
    websocket: WebSocket,
    camera_id: int = Query(..., description="ID ของกล้องที่ต้องการสตรีม"),
    db: Session = Depends(get_db)
):
    # ตรวจสอบว่ากล้องมีอยู่จริง
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        await websocket.close(code=1008, reason="Camera not found")
        return

    rtsp_link = camera.stream_url
    
    # เพิ่มตัวแปรควบคุมสถานะของ WebSocket
    websocket_active = True
    
    # รับการเชื่อมต่อ WebSocket
    await websocket.accept()
    print("INFO: connection open")
    
    # นำเข้าฟังก์ชัน process_rtsp จากไฟล์ yolo_realtime_worker
    try:
        from app.services.yolo_realtime_worker import process_rtsp, start_worker, stop_worker
        
        # เริ่ม worker thread ก่อน
        start_worker()
        
        # ใช้ process_rtsp จาก yolo_realtime_worker เพื่อประมวลผลภาพจาก RTSP
        stream_generator = process_rtsp(rtsp_link, save_annotated=False)
        
        while websocket_active:
            try:
                # ใช้ asyncio.wait_for เพื่อป้องกันการติดแชนแนล
                next_frame = next(stream_generator)
                detections, raw_base64, annotated_base64, _ = next_frame
                
                # ส่งทั้งภาพต้นฉบับและภาพที่มีการตรวจจับกลับไปที่ client
                try:
                    await asyncio.wait_for(
                        websocket.send_json({
                            "detections": detections,
                            "raw_image": raw_base64,
                            "annotated_image": annotated_base64
                        }),
                        timeout=0.5  # กำหนด timeout 0.5 วินาที
                    )
                    # หน่วงเวลาเล็กน้อย (20ms) เพื่อป้องกัน CPU ทำงานหนักเกินไป
                    await asyncio.sleep(0.02)
                except asyncio.TimeoutError:
                    # เกิด timeout - ลองตรวจสอบว่า WebSocket ยังเชื่อมต่ออยู่หรือไม่
                    print("⚠️ Timeout sending data to WebSocket")
                    websocket_active = False
                    break
                except WebSocketDisconnect:
                    print(f"🔌 WebSocket disconnected for camera {camera_id}")
                    websocket_active = False
                    break
                except Exception as e:
                    error_str = str(e).lower()
                    if "socket is closed" in error_str or "connection" in error_str or "websocket" in error_str:
                        print(f"🔌 WebSocket closed: {str(e)}")
                        websocket_active = False
                        break
                    else:
                        print(f"⚠️ Error sending data to WebSocket: {str(e)}")
                        # เพิ่มการตรวจสอบสถานะเชื่อมต่อ
                        websocket_active = False
                        break
            except StopIteration:
                print("🛑 Stream generator ended")
                websocket_active = False
                break
            except Exception as e:
                print(f"❌ Error in stream processing: {str(e)}")
                websocket_active = False
                break
                
    except WebSocketDisconnect:
        print(f"🔌 WebSocket disconnected for camera {camera_id}")
    except Exception as e:
        print(f"❌ Error in dual stream WebSocket: {str(e)}")
        traceback.print_exc()
    finally:
        # เพิ่มการหยุดทำงานของ worker thread เมื่อ WebSocket ถูกปิด
        try:
            stop_worker()
            print(f"✅ Stopped worker thread for camera {camera_id}")
        except Exception as e:
            print(f"⚠️ Error stopping worker: {str(e)}")
            
        # ปิดการเชื่อมต่อ WebSocket
        try:
            await websocket.close()
            print(f"✅ Closed WebSocket for camera {camera_id}")
        except Exception as e:
            print(f"⚠️ Couldn't close WebSocket: {str(e)}")
            pass

# ✅ สตรีมวิดีโจากกล้องพร้อมการตรวจจับแบบ direct real-time (ไม่ใช้ WebSocket)
@router.get("/realtime-detect-direct")
async def realtime_detect_direct(
    request: Request,
    camera_id: int = Query(..., description="ID ของกล้องที่ต้องการสตรีมพร้อมตรวจจับ"),
    token: str = Header(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
):
    """
    สตรีมวิดีโอจากกล้อง IP พร้อมการตรวจจับวัตถุแบบ real-time โดยตรงไม่ผ่าน WebSocket
    ส่งภาพที่มีการวาดกรอบแล้วกลับไปยัง client เลย ทำให้ดูเหมือนสตรีมภาพปกติ
    """
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
    print(f"🔍 Running direct YOLO streaming on device: {device} for camera {camera_id}")
    
    # เริ่มตรวจจับ
    detection_flags[camera_id] = True
    
    # ✅ ฟังก์ชันสร้าง Stream ที่มีการตรวจจับวัตถุแบบ direct
    async def generate():
        try:
            # ตัวแปรสำหรับการตรวจจับทุกๆ X วินาที
            last_detection_time = 0
            detection_interval = 0.5  # ทำการตรวจจับทุก 0.5 วินาที (2 FPS)
            last_detections = []  # เก็บผลการตรวจจับล่าสุด
            
            # ตั้งค่า temp directory
            temp_dir = "uploads/temp_realtime"
            os.makedirs(temp_dir, exist_ok=True)
            
            while detection_flags.get(camera_id, True):
                if camera_id not in video_captures or not video_captures[camera_id].isOpened():
                    print(f"⚠️ กล้อง {camera_id} ถูกปิด")
                    break
                    
                success, frame = video_captures[camera_id].read()
                if not success:
                    await asyncio.sleep(0.01)
                    continue
                
                # ตรวจสอบว่าถึงเวลาตรวจจับหรือยัง
                current_time = time.time()
                should_detect = (current_time - last_detection_time) >= detection_interval
                
                try:
                    # ถ้าถึงเวลาตรวจจับ
                    if should_detect:
                        last_detection_time = current_time
                        
                        # ทำสำเนาเฟรมเพื่อความปลอดภัย
                        frame_copy = frame.copy()
                        
                        # ลดขนาดเฟรม
                        frame_resized = cv2.resize(frame_copy, (320, 240))
                        
                        # ตรวจจับวัตถุด้วย yolo_worker.py ผ่าน subprocess
                        temp_path = os.path.join(temp_dir, f"temp_frame_{camera_id}_{current_time}.jpg")
                        cv2.imwrite(temp_path, frame_resized, [cv2.IMWRITE_JPEG_QUALITY, 50])
                        
                        try:
                            result = subprocess.run(
                                ["python", "app/services/yolo_worker.py", temp_path],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                timeout=5  # timeout 5 วินาที
                            )
                            
                            # ลบไฟล์ชั่วคราวทันที
                            try:
                                if os.path.exists(temp_path):
                                    os.remove(temp_path)
                            except:
                                pass
                                
                            if result.returncode == 0:
                                try:
                                    # แยก JSON จาก stdout
                                    start_index = result.stdout.find("{")
                                    end_index = result.stdout.rfind("}") + 1
                                    if start_index != -1 and end_index > 0:
                                        clean_json = result.stdout[start_index:end_index]
                                        output = json.loads(clean_json)
                                        last_detections = output.get("detections", [])
                                except:
                                    # ถ้าแยก JSON ไม่ได้ ใช้ผลการตรวจจับล่าสุด
                                    pass
                        except subprocess.TimeoutExpired:
                            # ถ้า timeout ให้ใช้ผลการตรวจจับล่าสุด
                            print(f"⚠️ YOLO detection timeout for camera {camera_id}")
                        except Exception as e:
                            print(f"❌ Error in YOLO detection: {str(e)}")
                    
                    # วาดกรอบรอบวัตถุที่ตรวจพบ (ทั้งกรณีตรวจจับใหม่และใช้ผลลัพธ์เดิม)
                    for detection in last_detections:
                        label = detection["label"]
                        conf = detection["confidence"]
                        box = detection["box"]
                        
                        x1, y1, x2, y2 = [int(float(coord)) for coord in box]
                        
                        # วาดกรอบ
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        
                        # วาดข้อความแสดงชื่อและความเชื่อมั่น
                        label_text = f"{label}: {conf:.2f}"
                        cv2.putText(frame, label_text, (x1, y1 - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    # เพิ่มข้อความแสดงจำนวนวัตถุที่ตรวจพบ
                    msg = f"พบวัตถุ: {len(last_detections)} ชิ้น"
                    cv2.putText(frame, msg, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                    
                    # ส่งภาพที่มีการวาดกรอบแล้วกลับไปยัง client
                    _, buffer = cv2.imencode('.jpg', frame)
                    yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n'
                    )
                    
                except Exception as e:
                    print(f"❌ Error in frame processing: {str(e)}")
                    traceback.print_exc()
                
                # รอสักครู่เพื่อไม่ให้ใช้ CPU มากเกินไป
                await asyncio.sleep(0.01)
                
        except Exception as e:
            print(f"❌ Error in direct detection streaming: {str(e)}")
            traceback.print_exc()
        finally:
            # หยุดการตรวจจับแต่ไม่ปิดกล้อง
            detection_flags[camera_id] = False
            print(f"🛑 Direct realtime detection stopped for camera {camera_id}")

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
        .options(joinedload(Order.customer))\
        .filter(or_(Order.assigned_to == None, Order.assigned_to == current_user.id))\
        .filter(Order.status.in_(["packing", "verifying"]))\
        .all()
    return [
        {
            "id": order.order_id,
            "email": order.customer.email if order.customer else None,
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
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4)),
):
    
    order = (
        db.query(Order)
        .options(
            joinedload(Order.customer),
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
    
    order.updated_at = datetime.utcnow()  # บันทึกเวลาที่ทำการ assign
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
        "customer_email": order.customer.email if order.customer else None,
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
    request: Request,
    verified: bool = Form(...),
    file: UploadFile = File(None),
    camera_id: int = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
):
    """
    ✅ พนักงานกดยืนยันสินค้าครบหรือไม่ครบ
    
    เมื่อพนักงานแพ็คสินค้าพบว่าสินค้าไม่ครบ:
    1. ระบบจะเปลี่ยนสถานะออเดอร์เป็น "confirmed" เพื่อส่งกลับให้พนักงานจัดเตรียมสินค้า
    2. คืนจำนวนสต็อกสินค้าที่เคยถูกหักไว้ตอนพนักงานจัดเตรียมกดอนุมัติออเดอร์
    3. ส่งการแจ้งเตือนไปยังแอดมินให้ทราบถึงสถานการณ์
    """
    order = db.query(Order).filter(Order.order_id == order_id, Order.assigned_to == current_user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not assigned to you")

    # ดึงหรือสร้างรูปภาพ
    has_image = False
    
    # เพิ่ม log เพื่อตรวจสอบ request
    print(f"Request headers: {request.headers}")
    print(f"Referer: {request.headers.get('referer', 'No referer')}")
      # กรณีมีไฟล์รูปภาพถูกส่งมา
    if file and file.filename:
        has_image = True
        upload_dir = "uploads/packed_orders"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{order_id}.jpg").replace("\\", "/")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        order.image_path = file_path
        # ถ้ามีการส่ง camera_id มาด้วย ให้บันทึกลงในออเดอร์
        if camera_id:
            order.camera_id = camera_id
            print(f"✅ Image uploaded from form data with camera_id {camera_id}: {file_path}")
        else:
            print(f"✅ Image uploaded from form data (no camera_id): {file_path}")
    
    # กรณีที่มีรูปภาพเก็บอยู่แล้ว
    elif order.image_path and os.path.exists(order.image_path):
        has_image = True
        print(f"✅ Using existing image: {order.image_path}")
    
    # กรณีต้องดึงรูปล่าสุดจากกล้องที่กำลังเปิดอยู่
    else:
        print("⚠️ No image found, attempting to capture from active camera")
        try:
            # ดูว่ามีกล้องที่เปิดอยู่หรือไม่
            cameras = db.query(Camera).all()
            for camera in cameras:
                camera_id = camera.id
                if camera_id in video_captures and video_captures[camera_id].isOpened():
                    # อ่านเฟรมล่าสุดจากกล้อง
                    success, frame = video_captures[camera_id].read()
                    if success:
                        # บันทึกรูปภาพ
                        upload_dir = "uploads/packed_orders"
                        os.makedirs(upload_dir, exist_ok=True)
                        file_path = os.path.join(upload_dir, f"{order_id}.jpg").replace("\\", "/")
                        cv2.imwrite(file_path, frame)
                        order.image_path = file_path
                        has_image = True
                        # บันทึก camera_id ที่ใช้ในการถ่ายภาพลงในออเดอร์
                        order.camera_id = camera_id
                        print(f"✅ Captured new image from camera {camera_id}: {file_path}")
                        break
        except Exception as e:
            print(f"❌ Error capturing frame from camera: {str(e)}")

    # ปรับเงื่อนไขการตรวจสอบ referer ให้ครอบคลุมทั้งกรณี dual-stream และกรณีที่มีการตรวจจับภาพแล้ว
    referer = str(request.headers.get('referer', ''))
    is_from_camera_page = any(keyword in referer.lower() for keyword in ['dual-stream', 'packing_dashboard', 'camera', 'detect'])
    
    if not has_image and not is_from_camera_page:
        print(f"❌ No image available and not from camera page. Referer: {referer}")
        raise HTTPException(status_code=400, detail="กรุณาตรวจจับสินค้าก่อนกดยืนยัน")
    else:
        print(f"✅ Verification proceeding. has_image={has_image}, is_from_camera_page={is_from_camera_page}")    # ✅ ถ้าสินค้าไม่ครบ → เปลี่ยนสถานะเป็น "confirmed" (ส่งกลับให้พนักงานจัดเตรียม) และคืนสต็อกสินค้า
    if not verified:
        # ดึงข้อมูลรายการสินค้าในออเดอร์เพื่อคืนสต็อก
        order_items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
        
        # คืนสต็อกสินค้าที่เคยถูกหักไป
        for item in order_items:
            product = db.query(Product).filter(Product.product_id == item.product_id).first()
            if product:
                product.stock += item.quantity
                print(f"✅ Restored {item.quantity} units to product {product.name} (ID: {product.product_id})")
        
    # เปลี่ยนสถานะเป็น "confirmed" เพื่อส่งกลับไปยังฝ่ายเตรียมสินค้า
        order.status = "confirmed"
        order.updated_at = datetime.utcnow()  # บันทึกเวลาที่ทำการยืนยัน
        db.commit()        # ✅ ส่ง HTTP Request ไปยัง Home เพื่อให้แจ้งเตือน Admin และพนักงานจัดเตรียม
        try:
            url = "http://192.168.0.44:8000/admin/trigger-notify"
            # url = "https://home.jintaphas.tech/admin/trigger-notify"
            payload = {
                "order_id": order_id,
                "reason": "สินค้าไม่ครบ ส่งกลับให้พนักงานจัดเตรียม"
            }
            resp = requests.post(url, json=payload, timeout=5)
            print("Notify admin response:", resp.status_code, resp.text)
            
            # แจ้งเตือนพนักงานจัดเตรียมด้วย WebSocket
            await notify_preparation(order_id, "สินค้าไม่ครบ กรุณาจัดเตรียมใหม่")
            
        except Exception as e:            print("Error calling home to notify staff:", e)
        return JSONResponse(content={
            "message": "Order sent back to preparation staff", 
            "order_id": order_id, 
            "status": "confirmed",
            "camera_id": order.camera_id
        })    # ✅ ถ้าสินค้าครบ → อัปเดตเป็น "completed"
    order.is_verified = verified
    order.status = "completed"
    order.updated_at = datetime.utcnow()  # บันทึกเวลาที่ทำการยืนยัน
    db.commit()

    return JSONResponse(content={
        "message": "Order verification updated", 
        "order_id": order_id, 
        "status": "completed",
        "camera_id": order.camera_id
    })

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
            joinedload(Order.customer),
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
            "total": item.total_item_price,
            "image_path": item.product.image_path if item.product else None        }
        for item in order.order_items
    ]
    
    return JSONResponse(content={
        "order_id": order.order_id,
        "customer_email": order.customer.email if order.customer else None,
        "total_price": order.total,
        "items": formatted_items,
        "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "image_path": order.image_path,
        "camera_id": order.camera_id  # เพิ่มข้อมูล camera_id
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
    # ดึงข้อมูลออเดอร์ตาม order_id
    order = db.query(Order).filter(Order.order_id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # ✅ เช็คว่ามีไฟล์ภาพจริงไหม
    if not order.image_path or not os.path.exists(order.image_path):
        raise HTTPException(status_code=404, detail="No packed order image found")

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

# กำหนด template สำหรับหน้าเว็บ
templates = Jinja2Templates(directory="app/templates")

# ✅ WebSocket endpoint สำหรับการตรวจจับแบบ real-time จากเว็บแคม
@router.websocket("/ws/webcam-detect")
async def websocket_webcam_detect(websocket: WebSocket, token: str = None):
    """
    WebSocket endpoint สำหรับรับภาพจากเว็บแคมและส่งผลการตรวจจับกลับ
    คล้ายกับที่ทำใน Flask แต่ใช้ WebSocket ซึ่งเร็วกว่า
    """
    await websocket.accept()
    device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
    print(f"🔍 New WebSocket connection for webcam detection. Using device: {device}")
    
    try:
        while True:
            # รับข้อมูลภาพ (base64) จาก client
            data = await websocket.receive_text()
            try:
                json_data = json.loads(data)
                image_data = json_data.get("image")
                
                # แปลงจาก base64 -> OpenCV image
                image_data = re.sub('^data:image/.+;base64,', '', image_data)
                image_bytes = base64.b64decode(image_data)
                np_arr = np.frombuffer(image_bytes, np.uint8)
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                
                if img is None or img.size == 0:
                    await websocket.send_json({"error": "ไม่สามารถแปลงรูปภาพได้"})
                    continue
                
                # ส่งภาพไปตรวจจับด้วย model
                results = model(img, conf=0.3)
                detections = []
                
                # วิเคราะห์ผลการตรวจจับ
                for result in results:
                    boxes = result.boxes
                    for box in boxes.data:
                        x1, y1, x2, y2, conf, cls = box.tolist()
                        label = model.names[int(cls)]
                        detections.append({
                            "label": label,
                            "confidence": float(conf),
                            "box": [float(x1), float(y1), float(x2), float(y2)],
                        })
                        
                        # วาดกรอบรอบวัตถุที่ตรวจพบ
                        cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                        
                        # วาดข้อความแสดงชื่อและความเชื่อมั่น
                        label_text = f"{label}: {conf:.2f}"
                        cv2.putText(img, label_text, (int(x1), int(y1) - 10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # แปลงภาพที่มีการวาดกรอบแล้วกลับเป็น base64
                _, buffer = cv2.imencode('.jpg', img)
                img_base64 = base64.b64encode(buffer).decode('utf-8')
                
                # ส่งผลลัพธ์กลับไปยัง client
                await websocket.send_json({
                    "image": img_base64,
                    "detections": detections,
                    "count": len(detections)
                })
                
            except json.JSONDecodeError:
                await websocket.send_json({"error": "ข้อมูล JSON ไม่ถูกต้อง"})
            except Exception as e:
                print(f"❌ Error processing frame: {str(e)}")
                await websocket.send_json({"error": f"เกิดข้อผิดพลาด: {str(e)}"})
    
    except WebSocketDisconnect:
        print("⚠️ WebSocket client disconnected")
    except Exception as e:
        print(f"❌ WebSocket error: {str(e)}")
        traceback.print_exc()

# ✅ WebSocket endpoint สำหรับการตรวจจับแบบ real-time จากกล้อง IP
@router.websocket("/ws/camera-detect")
async def websocket_camera_detect(websocket: WebSocket, camera_id: int = Query(...)):
    """
    WebSocket endpoint สำหรับตรวจจับวัตถุแบบ real-time จากกล้อง IP ที่เลือก
    ส่งผลลัพธ์กลับไปยัง client เพื่อแสดงในหน้าเว็บโดยตรง
    """
    global video_captures, detection_flags
    
    await websocket.accept()
    detection_interval = 0.5  # ทำการตรวจจับทุก 0.5 วินาที (2 FPS)
    
    # ดึงข้อมูลกล้องจาก DB
    try:
        db = next(get_db())
        camera = db.query(Camera).filter(Camera.id == camera_id).first()
        if not camera:
            await websocket.send_json({"error": "Camera not found"})
            await websocket.close()
            return
        
        rtsp_link = camera.stream_url
        
        # ตรวจสอบว่ากล้องถูกเปิดแล้วหรือยัง
        if camera_id not in video_captures or not video_captures[camera_id].isOpened():
            success = await start_camera(camera_id, rtsp_link)
            if not success:
                await websocket.send_json({"error": f"Failed to open camera {camera_id}"})
                await websocket.close()
                return
        
        device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        print(f"🔍 Starting WebSocket camera detection. Using device: {device} for camera {camera_id}")
        
        detection_flags[camera_id] = True
        last_detection_time = 0
        
        try:
            while detection_flags.get(camera_id, True):
                if camera_id not in video_captures or not video_captures[camera_id].isOpened():
                    print(f"⚠️ Camera {camera_id} is closed")
                    break
                
                success, frame = video_captures[camera_id].read()
                if not success:
                    await asyncio.sleep(0.01)
                    continue
                
                current_time = time.time()
                should_detect = (current_time - last_detection_time) >= detection_interval
                
                if should_detect:
                    last_detection_time = current_time
                    
                    try:
                        # ตรวจสอบความถูกต้องของเฟรม
                        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
                            print(f"⚠️ Invalid frame received from camera {camera_id}")
                            await asyncio.sleep(0.01)
                            continue
                        
                        try:
                            # ทำสำเนาเฟรมก่อนนำไปประมวลผล
                            frame_copy = frame.copy()
                            
                            # กำหนดตัวแปร detections ตั้งแต่ต้นเพื่อแก้ปัญหา "referenced before assignment"
                            detections = []
                            
                            # ใช้ subprocess เรียก yolo_worker.py เพื่อตรวจจับวัตถุ
                            # ซึ่งเป็นวิธีที่ทำงานได้จริงแล้วในฟังก์ชันอื่นๆ
                            # จำเป็นต้องเขียนลงไฟล์ชั่วคราว แต่คุณสามารถลดขนาดรูปภาพลงเพื่อให้เร็วขึ้น
                            
                            # สร้าง temp directory ถ้ายังไม่มี
                            temp_dir = "uploads/temp_realtime"
                            os.makedirs(temp_dir, exist_ok=True)
                            
                            # ลดขนาดเฟรมลงเพื่อให้การเขียนไฟล์และตรวจจับเร็วขึ้น (ลดลงมากขึ้น)
                            frame_resized = cv2.resize(frame_copy, (320, 240))
                            
                            # สร้างชื่อไฟล์ชั่วคราวที่ไม่ซ้ำกัน
                            temp_path = os.path.join(temp_dir, f"temp_frame_{camera_id}_{time.time()}.jpg")
                            
                            # บันทึกภาพลงไฟล์ชั่วคราวด้วยคุณภาพต่ำเพื่อให้เร็วขึ้น
                            cv2.imwrite(temp_path, frame_resized, [cv2.IMWRITE_JPEG_QUALITY, 50])
                            
                            # ใช้ subprocess เรียก yolo_worker.py ซึ่งทำงานได้แล้ว
                            # เพิ่ม timeout เป็น 10 วินาที
                            result = subprocess.run(
                                ["python", "app/services/yolo_worker.py", temp_path],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                timeout=10  # เพิ่ม timeout เป็น 10 วินาที
                            )
                            
                            # ลบไฟล์ชั่วคราวทันที
                            try:
                                if os.path.exists(temp_path):
                                    os.remove(temp_path)
                            except Exception as e:
                                print(f"⚠️ Warning: Failed to delete temporary file: {e}")
                            
                            if result.returncode != 0:
                                print(f"❌ YOLO worker error: {result.stderr}")
                                detections = []
                            else:
                                # แยก JSON จาก stdout
                                try:
                                    start_index = result.stdout.find("{")
                                    end_index = result.stdout.rfind("}") + 1
                                    if start_index == -1 or end_index == 0:
                                        detections = []
                                    else:
                                        clean_json = result.stdout[start_index:end_index]
                                        output = json.loads(clean_json)
                                        detections = output.get("detections", [])
                                except json.JSONDecodeError:
                                    print("❌ Failed to decode YOLO worker response")
                                    detections = []
                                    
                            # วาดกรอบรอบวัตถุที่ตรวจพบ
                            for detection in detections:
                                label = detection["label"]
                                conf = detection["confidence"]
                                box = detection["box"]
                                
                                x1, y1, x2, y2 = [int(float(coord)) for coord in box]
                                
                                # วาดกรอบ
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                
                                # วาดข้อความแสดงชื่อและความเชื่อมั่น
                                label_text = f"{label}: {conf:.2f}"
                                cv2.putText(frame, label_text, (x1, y1 - 10), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
                        except Exception as e:
                            print(f"❌ Error in detection: {str(e)}")
                            traceback.print_exc()
                        
                        # แปลงภาพที่มีการวาดกรอบแล้วเป็น base64
                        _, buffer = cv2.imencode('.jpg', frame)
                        img_base64 = base64.b64encode(buffer).decode('utf-8')
                        
                        # ส่งผลลัพธ์กลับไปยัง client
                        await websocket.send_json({
                            "image": img_base64,
                            "detections": detections,
                            "count": len(detections)
                        })
                        
                    except Exception as e:
                        print(f"❌ Error in detection: {str(e)}")
                        traceback.print_exc()
                
                # รอสักครู่เพื่อไม่ให้ใช้ CPU มากเกินไป
                await asyncio.sleep(0.01)
                
        except WebSocketDisconnect:
            print(f"⚠️ WebSocket client disconnected for camera {camera_id}")
        finally:
            # ไม่ปิดกล้องเมื่อ client disconnect เพราะอาจมีคนอื่นกำลังใช้อยู่
            detection_flags[camera_id] = False
    
    except Exception as e:
        print(f"❌ WebSocket camera detection error: {str(e)}")
        traceback.print_exc()
        try:
            await websocket.send_json({"error": f"Server error: {str(e)}"})
        except:
            pass
    finally:
        # ปิดการเชื่อมต่อ WebSocket
        try:
            await websocket.close()
        except:
            pass

# ✅ หน้าตรวจจับสินค้าแบบ real-time จากเว็บแคม
@router.get("/realtime-webcam", response_class=HTMLResponse)
async def get_realtime_webcam_page(
    request: Request,
    current_user: User = Depends(get_user_with_role_and_position_and_isActive(1, 4))
):
    """
    แสดงหน้า UI สำหรับการตรวจจับสินค้าแบบ real-time จากเว็บแคม
    """
    return templates.TemplateResponse("realtime_detection.html", {"request": request, "current_user": current_user})
