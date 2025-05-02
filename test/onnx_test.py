import onnxruntime as ort
session = ort.InferenceSession("./app/models/best.onnx")
print("Model loaded successfully")