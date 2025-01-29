from ultralytics import YOLOv10 as YOLO
import cv2
import os

# โหลดโมเดล YOLOv10
MODEL_PATH = "../app/models/best.pt"
try:
    model = YOLO(MODEL_PATH)
    print(f"✅ Loaded YOLOv10 model from {MODEL_PATH}")
except Exception as e:
    print(f"❌ Failed to load YOLOv10 model: {e}")
    exit()

# ฟังก์ชันทำนายผลจากภาพ
def predict_image(image_path):
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return

    print(f"📥 Loading image: {image_path}")
    img = cv2.imread(image_path)
    if img is None:
        print("❌ Failed to load image.")
        return

    try:
        # เริ่มการทำนาย
        print("🔍 Running YOLOv10 prediction...")
        results = model.predict(source=image_path, conf=0.3, iou=0.45, device='cpu')

        detections = []
        if results and hasattr(results[0], 'boxes') and results[0].boxes is not None:
            for box in results[0].boxes.data:
                x1, y1, x2, y2, conf, cls = box.tolist()
                label = model.names[int(cls)]
                detections.append({
                    "label": label,
                    "confidence": float(conf),
                    "box": [float(x1), float(y1), float(x2), float(y2)]
                })

        print(f"✅ Detections: {detections}")
        return detections

    except Exception as e:
        print(f"❌ Error during prediction: {e}")
        return


if __name__ == "__main__":
    # เส้นทางของภาพทดสอบ
    TEST_IMAGE_PATH = "D:/THESIS_FASTAPI_YOLO/uploads/packing_images/captured_image.png"  # ใส่ path ของภาพที่ต้องการทดสอบ
    predict_image(TEST_IMAGE_PATH)
