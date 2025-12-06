import os
import time
import base64
import requests
import torch
import uuid
from PIL import Image
from torchvision import transforms
from transformers import AutoModelForImageSegmentation
from threading import Lock

SD_API_URL = "http://localhost:5001/sdapi/v1/txt2img"
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

# Global Progress State
progress_store = {}
progress_lock = Lock()

class BackgroundRemover:
    def __init__(self):
        self.model = None
        self.transform = None
        self.load_model()

    def load_model(self):
        try:
            print(f"Loading RMBG-2.0 model on {DEVICE}...")
            self.model = AutoModelForImageSegmentation.from_pretrained(
                'briaai/RMBG-2.0', trust_remote_code=True
            ).eval().to(DEVICE)
            
            self.transform = transforms.Compose([
                transforms.Resize((1024, 1024)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
            ])
            print("RMBG model loaded successfully.")
        except Exception as e:
            print(f"Warning: Failed to load RMBG model. BG removal will fail. Error: {e}")
            self.model = None

    def process(self, input_path: str, output_path: str):
        if not self.model:
            raise RuntimeError("RMBG model is not loaded.")

        try:
            image = Image.open(input_path).convert("RGB")
            orig_size = image.size
            
            input_tensor = self.transform(image).unsqueeze(0).to(DEVICE)

            with torch.no_grad():
                preds = self.model(input_tensor)[-1].sigmoid().cpu()
            
            pred = preds[0].squeeze()
            pred_pil = transforms.ToPILImage()(pred)
            mask = pred_pil.resize(orig_size)
            image.putalpha(mask)
            
            image.save(output_path, "PNG")
            return True
        except Exception as e:
            print(f"Error removing background: {e}")
            raise e

bg_remover = BackgroundRemover()

def update_progress(task_id, status, percentage, current_count=0, total=0):
    with progress_lock:
        progress_store[task_id] = {
            "status": status,
            "progress": percentage,
            "current": current_count,
            "total": total,
            "timestamp": time.time()
        }

def generate_jewelry_images(task_id: str, prompt: str, num_images: int, remove_bg: bool, save_history_callback):
    generated_results = []
    
    update_progress(task_id, "starting", 0, 0, num_images)

    for i in range(num_images):
        update_progress(task_id, f"generating {i+1}/{num_images}", int((i / num_images) * 80), i, num_images)
        
        payload = {
            "prompt": prompt,
            "negative_prompt": "ugly, deformed, censored, blur, low quality, watermark, text",
            "steps": 20,
            "width": 512,
            "height": 512,
        }

        try:
            response = requests.post(SD_API_URL, json=payload, timeout=60)
            if response.status_code != 200:
                raise Exception(f"SD API Error: {response.status_code}")
            
            data = response.json()
            if not data.get("images"):
                raise Exception("No images returned from API")

            image_bytes = base64.b64decode(data["images"][0])
            filename = f"gen_{uuid.uuid4()}.png"
            filepath = os.path.join("uploads", filename)
            
            with open(filepath, "wb") as f:
                f.write(image_bytes)
            
            save_history_callback(filename, prompt)
            generated_results.append({"filename": filename, "prompt": prompt})

            if remove_bg:
                update_progress(task_id, f"removing bg {i+1}/{num_images}", int((i / num_images) * 90), i, num_images)
                
                bg_filename = f"nobg_{filename}"
                bg_filepath = os.path.join("uploads", bg_filename)
                
                bg_remover.process(filepath, bg_filepath)
                
                save_history_callback(bg_filename, f"[BG Removed] {prompt}")
                generated_results.append({"filename": bg_filename, "prompt": f"[BG Removed] {prompt}"})

        except Exception as e:
            print(f"Generation error: {e}")
            update_progress(task_id, f"error: {str(e)}", 100)
            return

    with progress_lock:
        progress_store[task_id] = {
            "status": "completed",
            "progress": 100,
            "current": num_images,
            "total": num_images,
            "results": generated_results,
            "timestamp": time.time()
        }