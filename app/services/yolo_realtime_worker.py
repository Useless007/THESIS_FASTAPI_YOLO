import sys
import json
import cv2
import numpy as np
import torch
from ultralytics import YOLOv10 as YOLO
import os
import time
import base64

MODEL_PATH = "./app/models/best.pt"
model = YOLO(MODEL_PATH)

def process_rtsp(cam_ip, save_annotated=True):
    """
    Process RTSP stream from camera for real-time object detection
    
    Args:
        cam_ip (str): Camera IP address or RTSP URL
        save_annotated (bool): Whether to save annotated frames
        
    Returns:
        Generator that yields tuples (detections, raw_frame, annotated_frame)
    """
    # Check if CUDA (GPU) is available
    device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
    print(f"🔍 Running YOLO on device: {device}")
    
    # Open RTSP stream
    cap = cv2.VideoCapture(cam_ip)
    
    if not cap.isOpened():
        raise Exception(f"Failed to open RTSP stream at {cam_ip}")
    
    # Create temp directory for annotated frames if needed
    if save_annotated:
        temp_dir = "./uploads/temp_realtime"
        os.makedirs(temp_dir, exist_ok=True)
    
    try:
        while True:
            ret, frame = cap.read()
            
            if not ret:
                print(f"⚠️ Failed to read frame from {cam_ip}")
                time.sleep(0.5)  # Pause briefly before retry
                continue
            
            # Get raw frame in base64 for streaming
            _, raw_buffer = cv2.imencode('.jpg', frame)
            raw_base64 = base64.b64encode(raw_buffer).decode('utf-8')
            
            # Predict using the model
            results = model.predict(source=frame, conf=0.1, iou=0.45, stream=False, device=device)
            
            # Copy frame for drawing
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
            
            # Convert annotated frame to base64 for streaming
            _, annotated_buffer = cv2.imencode('.jpg', annotated_frame)
            annotated_base64 = base64.b64encode(annotated_buffer).decode('utf-8')
            
            # Clean GPU memory if CUDA is available
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Save the annotated frame if requested
            annotated_path = None
            if save_annotated:
                timestamp = int(time.time() * 1000)
                annotated_path = f"{temp_dir}/frame_{timestamp}.jpg"
                cv2.imwrite(annotated_path, annotated_frame)
            
            # Yield detections and both frames (raw and annotated)
            yield detections, raw_base64, annotated_base64, annotated_path
    
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
        # For backward compatibility with the existing code
        # This part remains unchanged, but uses the first frame only
        for detections, _, annotated_base64, annotated_path in process_rtsp(image_path):
            # Return both detections and path to annotated image
            sys.stdout.write(json.dumps({
                "detections": detections,
                "annotated_image": annotated_path
            }))
            break  # Process only the first frame
    except Exception as e:
        sys.stderr.write(json.dumps({"error": str(e)}))
        sys.exit(1)