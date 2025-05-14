import sys
import json
import cv2
import numpy as np
import torch
from ultralytics import YOLOv10 as YOLO
import os
import time
import base64
import threading
import queue

MODEL_PATH = "./app/models/best.pt"
model = None
model_lock = threading.Lock()

# คิวสำหรับเก็บเฟรมที่ต้องการประมวลผล
frame_queue = queue.Queue(maxsize=5)  # จำกัดขนาดคิวไม่เกิน 5 เฟรม
result_queue = queue.Queue()

# ตัวแปรควบคุมสถานะการประมวลผล
processing = False
processing_lock = threading.Lock()

def get_model():
    """ฟังก์ชันสำหรับเรียกใช้โมเดล YOLO ตาม lazy loading pattern"""
    global model
    with model_lock:
        if model is None:
            # Check if CUDA (GPU) is available
            device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
            print(f"🔍 Loading YOLO model on device: {device}")
            model = YOLO(MODEL_PATH)
    return model

def worker_thread():
    """
    Worker thread ที่ทำงานแยกจาก thread หลัก
    จะประมวลผลเฟรมจากคิวและส่งผลลัพธ์ไปที่คิวผลลัพธ์
    """
    global processing
    try:
        with processing_lock:
            processing = True
        
        # โหลดโมเดลถ้ายังไม่ได้โหลด
        yolo_model = get_model()
        
        # Check if CUDA (GPU) is available
        device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        
        while processing:
            try:
                # รับเฟรมจากคิวโดยรออย่างมากไม่เกิน 1 วินาที
                frame, rtsp_url, save_annotated = frame_queue.get(timeout=1.0)
                
                # ทำการประมวลผล YOLO
                results = yolo_model.predict(source=frame, conf=0.1, iou=0.45, stream=False, device=device)
                
                # สร้างก๊อปปี้ของเฟรมสำหรับวาด
                annotated_frame = frame.copy()
                
                detections = []
                for result in results:
                    for box in result.boxes.data:
                        x1, y1, x2, y2, conf, cls = box.tolist()
                        
                        if conf > 0.6:
                            # Get integer coordinates for drawing
                            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                            label = yolo_model.names[int(cls)]
                            
                            # Draw bounding box
                            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            
                            # Add label with confidence score
                            text = f"{label}: {conf:.2f}"
                            font = cv2.FONT_HERSHEY_SIMPLEX
                            text_size = cv2.getTextSize(text, font, 0.5, 2)[0]
                            
                            # Background for text (for better visibility)
                            cv2.rectangle(annotated_frame, (x1, y1 - text_size[1] - 10), (x1 + text_size[0], y1), (0, 255, 0), -1)
                            
                            # Text
                            cv2.putText(annotated_frame, text, (x1, y1 - 5), font, 0.5, (0, 0, 0), 2)
                            
                            detections.append({
                                "label": label,
                                "confidence": float(conf),
                                "box": [float(x1), float(y1), float(x2), float(y2)],
                            })
                
                # แปลงเฟรมเป็น base64
                _, raw_buffer = cv2.imencode('.jpg', frame)
                raw_base64 = base64.b64encode(raw_buffer).decode('utf-8')
                
                # แปลงเฟรมที่มีการวาดกรอบแล้วเป็น base64
                _, annotated_buffer = cv2.imencode('.jpg', annotated_frame)
                annotated_base64 = base64.b64encode(annotated_buffer).decode('utf-8')
                
                # ล้างหน่วยความจำ GPU ถ้ามีการใช้ CUDA
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                # Save the annotated frame if requested
                annotated_path = None
                if save_annotated:
                    temp_dir = "./uploads/temp_realtime"
                    os.makedirs(temp_dir, exist_ok=True)
                    timestamp = int(time.time() * 1000)
                    annotated_path = f"{temp_dir}/frame_{timestamp}.jpg"
                    cv2.imwrite(annotated_path, annotated_frame)
                
                # ใส่ผลลัพธ์ลงในคิวผลลัพธ์
                result_queue.put((detections, raw_base64, annotated_base64, annotated_path))
                
                # แจ้ง frame_queue ว่าเราได้ประมวลผลเฟรมเสร็จแล้ว
                frame_queue.task_done()
                
            except queue.Empty:
                # ถ้าคิวว่าง ก็ข้ามไป ไม่ต้องทำอะไร
                continue
            except Exception as e:
                print(f"❌ Error in worker thread: {str(e)}")
                # ใส่ผลลัพธ์ว่างเพื่อให้รู้ว่ามีข้อผิดพลาด
                result_queue.put(([], "", "", None))
                # แจ้ง frame_queue ว่าเราได้ประมวลผลเฟรมเสร็จแล้ว
                try:
                    frame_queue.task_done()
                except:
                    pass
    
    except Exception as e:
        print(f"❌ Fatal error in worker thread: {str(e)}")
    finally:
        with processing_lock:
            processing = False

def start_worker():
    """เริ่มการทำงานของ worker thread ถ้ายังไม่ได้เริ่ม"""
    global processing
    with processing_lock:
        if not processing:
            # เริ่ม worker thread
            worker = threading.Thread(target=worker_thread, daemon=True)
            worker.start()
            return True
    return False

def stop_worker():
    """หยุดการทำงานของ worker thread"""
    global processing
    with processing_lock:
        processing = False
    # รอให้คิวว่างเปล่า
    if not frame_queue.empty():
        try:
            frame_queue.join()
        except:
            pass

def process_rtsp(cam_ip, save_annotated=True):
    """
    Process RTSP stream from camera for real-time object detection
    
    Args:
        cam_ip (str): Camera IP address or RTSP URL
        save_annotated (bool): Whether to save annotated frames
        
    Returns:
        Generator that yields tuples (detections, raw_frame, annotated_frame)
    """
    # เริ่ม worker thread ถ้ายังไม่ได้เริ่ม
    start_worker()
    
    # Open RTSP stream
    cap = cv2.VideoCapture(cam_ip)
    
    if not cap.isOpened():
        raise Exception(f"Failed to open RTSP stream at {cam_ip}")
    
    try:
        while True:
            ret, frame = cap.read()
            
            if not ret:
                print(f"⚠️ Failed to read frame from {cam_ip}")
                time.sleep(0.5)  # Pause briefly before retry
                continue
            
            # ถ้าคิวไม่เต็ม ให้ใส่เฟรมเข้าไปในคิว
            try:
                if not frame_queue.full():
                    frame_queue.put((frame, cam_ip, save_annotated), block=False)
            except queue.Full:
                # ถ้าคิวเต็ม ข้ามไปเฟรมถัดไป
                pass
            
            # ตรวจสอบว่ามีผลลัพธ์หรือไม่
            try:
                detections, raw_base64, annotated_base64, annotated_path = result_queue.get(block=False)
                result_queue.task_done()
                yield detections, raw_base64, annotated_base64, annotated_path
            except queue.Empty:
                # ถ้าไม่มีผลลัพธ์ ให้สร้างเฟรมเปล่า
                _, raw_buffer = cv2.imencode('.jpg', frame)
                raw_base64 = base64.b64encode(raw_buffer).decode('utf-8')
                yield [], raw_base64, raw_base64, None
            
            # นอนสักครู่เพื่อไม่ให้ CPU ทำงานหนักเกินไป
            time.sleep(0.05)
    
    except Exception as e:
        print(f"❌ Error in RTSP processing: {str(e)}")
    finally:
        # Release resources
        cap.release()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No image path provided"}), file=sys.stderr)
        sys.exit(1)

    image_path = sys.argv[1]
    try:
        # สร้าง model instance
        model = get_model()
        
        # อ่านรูปภาพ
        frame = cv2.imread(image_path)
        if frame is None:
            raise ValueError(f"Failed to read image: {image_path}")
        
        # ประมวลผล YOLO โดยตรงไม่ผ่าน worker thread
        device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        results = model.predict(source=frame, conf=0.1, iou=0.45, stream=False, device=device)
        
        # สร้างก๊อปปี้ของเฟรมสำหรับวาด
        annotated_frame = frame.copy()
        
        detections = []
        for result in results:
            for box in result.boxes.data:
                x1, y1, x2, y2, conf, cls = box.tolist()
                
                if conf > 0.3:
                    # Get integer coordinates for drawing
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    label = model.names[int(cls)]
                    
                    # Draw bounding box
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    # Add label with confidence score
                    text = f"{label}: {conf:.2f}"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    text_size = cv2.getTextSize(text, font, 0.5, 2)[0]
                    
                    # Background for text (for better visibility)
                    cv2.rectangle(annotated_frame, (x1, y1 - text_size[1] - 10), (x1 + text_size[0], y1), (0, 255, 0), -1)
                    
                    # Text
                    cv2.putText(annotated_frame, text, (x1, y1 - 5), font, 0.5, (0, 0, 0), 2)
                    
                    detections.append({
                        "label": label,
                        "confidence": float(conf),
                        "box": [float(x1), float(y1), float(x2), float(y2)],
                    })
        
        # บันทึกภาพที่มีการวาดกรอบแล้ว
        temp_dir = "./uploads/temp_realtime"
        os.makedirs(temp_dir, exist_ok=True)
        timestamp = int(time.time() * 1000)
        annotated_path = f"{temp_dir}/frame_{timestamp}.jpg"
        cv2.imwrite(annotated_path, annotated_frame)
        
        # Return both detections and path to annotated image
        sys.stdout.write(json.dumps({
            "detections": detections,
            "annotated_image": annotated_path
        }))
    except Exception as e:
        sys.stderr.write(json.dumps({"error": str(e)}))
        sys.exit(1)