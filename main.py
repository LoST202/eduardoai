from fastapi import FastAPI, File, UploadFile, Form, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import os
import uuid
import zipfile
import io
import time
import threading

from services import bg_remover, generate_jewelry_images, progress_store, progress_lock
from utils import (
    UPLOAD_DIR, load_history, save_history_item, clear_history_data, 
    get_unique_filename, save_upload_file, cleanup_file
)

app = FastAPI(title="JewelGen AI")

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
templates = Jinja2Templates(directory="templates")

class BgRemoveRequest(BaseModel):
    filename: str

def cleanup_old_tasks_loop():
    while True:
        time.sleep(600)
        current_time = time.time()
        with progress_lock:
            to_remove = [k for k, v in progress_store.items() 
                         if current_time - v.get("timestamp", 0) > 900]
            for k in to_remove:
                del progress_store[k]

cleanup_thread = threading.Thread(target=cleanup_old_tasks_loop, daemon=True)
cleanup_thread.start()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/history")
async def get_history_api():
    return {"history": load_history()}

@app.post("/clear-history")
async def clear_history_api():
    clear_history_data()
    return {"success": True}

@app.post("/generate-multiple")
async def generate_multiple(
    background_tasks: BackgroundTasks,
    prompt: str = Form(...),
    num_images: int = Form(1),
    remove_background: str = Form(default="false")
):
    if not (1 <= num_images <= 10):
        return JSONResponse(status_code=400, content={"error": "Image count must be 1-10"})
    
    task_id = str(uuid.uuid4())
    should_remove_bg = remove_background.lower() == "true"
    
    background_tasks.add_task(
        generate_jewelry_images, 
        task_id, 
        prompt, 
        num_images, 
        should_remove_bg, 
        save_history_item
    )
    
    return {"task_id": task_id, "message": "Generation started"}

@app.get("/progress/{task_id}")
async def get_progress(task_id: str):
    with progress_lock:
        data = progress_store.get(task_id)
    
    if not data:
        return {"status": "not_found", "progress": 0}
    return data

@app.post("/cleanup-progress/{task_id}")
async def cleanup_progress(task_id: str):
    with progress_lock:
        if task_id in progress_store:
            del progress_store[task_id]
    return {"success": True}

@app.post("/remove-background")
async def remove_background_upload(image_file: UploadFile = File(...)):
    if not bg_remover.model:
        return JSONResponse(status_code=503, content={"error": "Model not loaded"})

    temp_filename = get_unique_filename(image_file.filename.split('.')[-1])
    temp_path = os.path.join(UPLOAD_DIR, temp_filename)
    
    try:
        content = await image_file.read()
        save_upload_file(content, temp_filename)
        
        output_filename = f"nobg_{temp_filename}"
        output_path = os.path.join(UPLOAD_DIR, output_filename)
        
        await app.router.startup()
        

        bg_remover.process(temp_path, output_path)
        
        cleanup_file(temp_path)
        
        save_history_item(output_filename, f"Background removed from upload")
        return {"filename": output_filename, "message": "Success"}
        
    except Exception as e:
        cleanup_file(temp_path)
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/remove-background-existing")
async def remove_background_existing(req: BgRemoveRequest):
    if not bg_remover.model:
        return JSONResponse(status_code=503, content={"error": "Model not loaded"})

    safe_filename = os.path.basename(req.filename)
    input_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    output_filename = f"nobg_{safe_filename}"
    output_path = os.path.join(UPLOAD_DIR, output_filename)
    
    try:
        bg_remover.process(input_path, output_path)
        save_history_item(output_filename, f"[BG Removed] Original: {safe_filename}")
        return {"filename": output_filename, "message": "Success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/download/{filename}")
async def download_file(filename: str):
    safe_filename = os.path.basename(filename)
    path = os.path.join(UPLOAD_DIR, safe_filename)
    if os.path.exists(path):
        return FileResponse(path, filename=safe_filename)
    return JSONResponse(status_code=404, content={"error": "File not found"})

@app.get("/download-zip")
async def download_zip(files: str = ""):
    if files:
        file_list = files.split(",")
    else:
        history = load_history()
        file_list = [h['filename'] for h in history]
        
    if not file_list:
        return JSONResponse(status_code=400, content={"error": "No files to download"})

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for fname in file_list:
            safe_fname = os.path.basename(fname)
            fpath = os.path.join(UPLOAD_DIR, safe_fname)
            if os.path.exists(fpath):
                zip_file.write(fpath, safe_fname)
                
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer, 
        media_type='application/zip', 
        headers={"Content-Disposition": "attachment; filename=jewelry_images.zip"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)