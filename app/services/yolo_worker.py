import sys
import json
import cv2
import numpy as np
import torch
from ultralytics import YOLOv10 as YOLO
import os

MODEL_PATH = "app/models/best.pt"
model = YOLO(MODEL_PATH)

def process_image(image_path, save_annotated=True):
    # Check if CUDA (GPU) is available
    device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
    print(f"🔍 Running YOLO on device: {device}")
    
    # Predict using the model
    results = model.predict(source=image_path, conf=0.1, iou=0.45, stream=False, device=device)
    
    # Load the image for drawing
    image = cv2.imread(image_path)
    
    detections = []
    for result in results:
        for box in result.boxes.data:
            x1, y1, x2, y2, conf, cls = box.tolist()
            if conf > 0.3:
                # Get integer coordinates for drawing
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                label = model.names[int(cls)]
                
                # Draw bounding box
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                # Add label with confidence score
                text = f"{label}: {conf:.2f}"
                font = cv2.FONT_HERSHEY_SIMPLEX
                text_size = cv2.getTextSize(text, font, 0.5, 2)[0]
                
                # Background for text (for better visibility)
                cv2.rectangle(image, (x1, y1 - text_size[1] - 10), (x1 + text_size[0], y1), (0, 255, 0), -1)
                # Text
                cv2.putText(image, text, (x1, y1 - 5), font, 0.5, (0, 0, 0), 2)
                
                detections.append({
                    "label": label,
                    "confidence": float(conf),
                    "box": [float(x1), float(y1), float(x2), float(y2)],
                })
    
    # Clean GPU memory if CUDA is available
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    # Save the annotated image
    if save_annotated:
        output_path = image_path.replace('.', '_annotated.')
        cv2.imwrite(output_path, image)
    
    return detections, output_path if save_annotated else None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No image path provided"}), file=sys.stderr)
        sys.exit(1)

    image_path = sys.argv[1]
    try:
        detections, annotated_path = process_image(image_path)
        # Return both detections and path to annotated image
        sys.stdout.write(json.dumps({
            "detections": detections,
            "annotated_image": annotated_path
        }))
    except Exception as e:
        sys.stderr.write(json.dumps({"error": str(e)}))
        sys.exit(1)