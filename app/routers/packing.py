# app/routers/packing.py

from concurrent.futures import ThreadPoolExecutor,ProcessPoolExecutor
import asyncio
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException,Query,Header, Response
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from app.models.user import User
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
RTSP_LINK = 'rtsp://admin:R2teamza99@192.168.0.242:10544/tcp/av0_0'

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

async def start_camera():
    global video_capture
    print("🔍 Trying to open RTSP stream...")

    # ปิดกล้องก่อนเปิดใหม่ (ถ้ามี)
    if video_capture is not None:
        video_capture.release()
        video_capture = None
        await asyncio.sleep(1)

    retry_count = 0
    max_retries = 5
    while retry_count < max_retries:
        video_capture = cv2.VideoCapture(RTSP_LINK, cv2.CAP_FFMPEG)
        await asyncio.sleep(2)  # รอให้กล้องเริ่มทำงาน
        if video_capture.isOpened():
            print("✅ Camera stream started successfully.")
            return True
        else:
            print(f"⚠️ Attempt {retry_count + 1} to open camera stream failed.")
            video_capture.release()  # ปิดถ้าเปิดไม่สำเร็จ
            video_capture = None
        retry_count += 1

    print("❌ Failed to open RTSP stream after multiple retries.")
    return False

async def stop_camera():
    global video_capture
    if video_capture and video_capture.isOpened():
        print("🛑 Stopping camera stream...")
        video_capture.release()
        cv2.destroyAllWindows()
        video_capture = None  # ปิดกล้องแล้วตั้งค่าให้เป็น None
        await asyncio.sleep(1)  # ให้เวลากล้องปิดอย่างสมบูรณ์
    print("✅ Camera resources released.")


# ✅ แคปภาพจากกล้อง
@router.get("/snapshot")
async def snapshot():
    global video_capture
    # ถ้า video_capture ยังไม่เปิด ก็ต้อง start_camera() ก่อน
    if video_capture is None or not video_capture.isOpened():
        raise HTTPException(status_code=400, detail="Camera is not opened")

    success, frame = video_capture.read()
    if not success:
        raise HTTPException(status_code=500, detail="Cannot read frame from camera")

    # encode เป็น jpg
    _, buffer = cv2.imencode('.jpg', frame)

    return Response(content=buffer.tobytes(), media_type="image/jpeg")


# ✅ สตรีมวิดีโอจากกล้อง
@router.get("/stream")
async def stream_video(
    token: str = Header(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "packing staff"))
):
    global video_capture

    await start_camera()

    # ล็อกไม่ให้สตรีมซ้อน
    locked = stream_lock.locked()
    if locked:
        raise HTTPException(status_code=429, detail="Stream is already in use.")

    # โค้ดหลังจากนี้ให้อยู่ระดับเดียวกับ if locked:

    async def generate():
        try:
            while True:
                if video_capture is None or not video_capture.isOpened():
                    print("⚠️ Camera is not opened or has been stopped.")
                    break

                success, frame = video_capture.read()
                if not success:
                    await asyncio.sleep(0.01)
                    continue

                # เข้ารหัสภาพเป็น .jpg
                _, buffer = cv2.imencode('.jpg', frame)

                # ส่งข้อมูลรูปภาพ (mjpeg)
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n'
                )

                await asyncio.sleep(0.01)
        except Exception as e:
            print(f"❌ Error during stream generation: {e}")
        finally:
            # ถ้า generator หลุด/จบไม่ว่ากรณีใด ให้ stop_camera()
            await stop_camera()

    response = StreamingResponse(
        generate(), 
        media_type="multipart/x-mixed-replace;boundary=frame"
    )
    # response.headers["Access-Control-Allow-Origin"] = "*"
    # response.headers["Access-Control-Allow-Headers"] = "*"
    return response



# ✅ ปิดกล้อง
@router.get("/stop-stream")
async def stop_stream(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_with_role_and_position_and_isActive("employee", "packing staff"))
):
    print("🔄 Request received to stop camera stream.")
    
    # หยุดการสตรีมก่อน
    await stop_camera()

    # แจ้งให้ Client หยุดรับข้อมูล
    response = JSONResponse(content={"message": "🛑 Camera stream stopped successfully."})
    response.headers["Connection"] = "close"
    return response


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
