
import sys
import os
from pathlib import Path

# Disable online checks to prevent hanging
os.environ["ULTRALYTICS_OFFLINE"] = "True"
os.environ["YOLO_VERBOSE"] = "False"

# Add backend to path
_BACKEND = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(_BACKEND))

from config import cfg
from utils.logger import get_logger

log = get_logger("test_yolo")

def test_load():
    try:
        from ultralytics import YOLO
        import torch
        
        model_path = cfg.YOLO_MODEL_PATH
        log.info(f"Loading model from {model_path}")
        
        model = YOLO(str(model_path))
        log.info("Model loaded into RAM.")
        
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        log.info(f"Moving to device: {device}")
        model.to(device)
        log.info("Model on device.")
        
        log.info("Running dummy inference...")
        import numpy as np
        model.predict(np.zeros((320,320,3), dtype=np.uint8), verbose=False)
        log.info("Inference OK.")
        
    except Exception as e:
        log.error(f"Failed: {e}")

if __name__ == "__main__":
    test_load()
