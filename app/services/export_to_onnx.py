# app/services/export_to_onnx.py
# Script สำหรับแปลงโมเดล YOLOv10 เป็น ONNX format

import torch
import os
from ultralytics import YOLO
import logging
from pathlib import Path

def export_model_to_onnx(pt_model_path: str, output_path: str):
    """
    Export a YOLO model from .pt format to ONNX format for running in browsers with ONNX Runtime Web
    
    Args:
        pt_model_path (str): Path to the .pt model file
        output_path (str): Path where the ONNX model should be saved
    """
    try:
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Load the model
        logging.info(f"🔄 Loading model from {pt_model_path}")
        model = YOLO(pt_model_path)
        
        # Export to ONNX format with appropriate settings for web compatibility
        logging.info(f"🔄 Exporting model to ONNX format at {output_path}")
        
        # Export with specific settings for web compatibility
        success = model.export(format="onnx", 
                      imgsz=640,  # Standard YOLO input size
                      half=False,  # Don't use half precision to ensure compatibility
                      simplify=True,  # Simplify the model
                      opset=12,  # Use ONNX opset 12 for better compatibility
                      dynamic=True)
        
        if success:
            logging.info(f"✅ Successfully exported model to {output_path}")
            return True
        else:
            logging.error("❌ Failed to export model")
            return False
            
    except Exception as e:
        logging.error(f"❌ Error during model export: {str(e)}")
        raise Exception(f"Failed to export model: {str(e)}")

if __name__ == "__main__":
    # Example usage:
    # python export_to_onnx.py
    logging.basicConfig(level=logging.INFO)
    
    # Default paths
    MODEL_PATH = os.path.join("app", "models", "best.pt")
    OUTPUT_PATH = os.path.join("app", "models", "best.onnx")
    
    if not os.path.exists(MODEL_PATH):
        logging.error(f"❌ Model file not found at {MODEL_PATH}")
    else:
        export_model_to_onnx(MODEL_PATH, OUTPUT_PATH)