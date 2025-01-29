import sys
import json
from ultralytics import YOLOv10 as YOLO

MODEL_PATH = "app/models/best.pt"
model = YOLO(MODEL_PATH)

def process_image(image_path):
    results = model.predict(source=image_path, conf=0.1, iou=0.45, stream=False, device='cpu')
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
    return detections

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No image path provided"}), file=sys.stderr)
        sys.exit(1)

    image_path = sys.argv[1]
    try:
        detections = process_image(image_path)
        # Ensure only JSON is printed
        sys.stdout.write(json.dumps({"detections": detections}))
    except Exception as e:
        sys.stderr.write(json.dumps({"error": str(e)}))
        sys.exit(1)
