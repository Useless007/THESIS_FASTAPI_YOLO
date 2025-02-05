from fastapi import FastAPI
from app import middleware
from app.routers.packing import router as packing_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

# สร้าง FastAPI instance สำหรับ packing server
app = FastAPI(title="Packing Server", version="1.0.0")

# รวม router ที่เกี่ยวข้องกับ packing
app.include_router(packing_router)

# เพิ่ม CORS Middleware
app.add_middleware(
    CORSMiddleware,
    # allow_origins=["*"],
    allow_origins=["https://home.jintaphas.tech"], # domain name
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE","OPTION"],
    allow_headers=["*"],
)

# ให้บริการไฟล์ static และ uploads (ถ้าจำเป็น)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# middleware ต่างๆ
app.add_middleware(middleware.AuthRedirectMiddleware)
app.add_middleware(middleware.ExceptionLoggingMiddleware)
app.add_middleware(middleware.BlockMaliciousRequestsMiddleware)
app.add_middleware(middleware.FilterInvalidHTTPMethodMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["home.jintaphas.tech", "thesis-api.jintaphas.tech", "127.0.0.1","192.168.0.44"])
# app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])



# รัน server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server_packing:app", host="0.0.0.0", port=8001, reload=True)
