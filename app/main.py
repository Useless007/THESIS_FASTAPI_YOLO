# app/main.py

from fastapi import FastAPI,Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routers import user, product , public, admin
from fastapi.openapi.utils import get_openapi
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
import re,logging


# ตั้งค่า Logger
logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)

# ตั้งค่า Templates Directory
templates = Jinja2Templates(directory="app/templates")

app = FastAPI()

# การตั้งค่า security
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="FastAPI with JWT Auth for Jintaphas's & Akaradej's Project",
        version="1.0.0",
        description="โปรเจคนี้ถูกจัดทำขึ้นเพื่อการศึกษาเท่านั้น",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# รวม router สำหรับ customer
app.include_router(user.router)
app.include_router(user.protected_router)
app.include_router(user.admin_router)
app.include_router(product.router)
app.include_router(public.router)
app.include_router(admin.router)

# CORS middleware เพื่อให้ Swagger UI สามารถทำงานได้
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class FilterInvalidHTTPMethodMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
        
        if request.method not in valid_methods:
            logger.warning(f"🚨 Invalid HTTP Method: {request.client.host} | {request.method} {request.url}")
            raise HTTPException(status_code=405, detail="❌ Invalid HTTP Method")
        
        return await call_next(request)
    
# Middleware สำหรับบล็อกคำสั่งอันตราย
class BlockMaliciousRequestsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        url_path = request.url.path
        query_params = request.url.query

        # ตรวจจับ Command Injection
        command_injection_pattern = re.compile(
            r"(;|&&|\|\||`|>|<|\$\(.*\)|\b(wget|curl|chmod|rm|cd)\b)"
        )
        
        # ตรวจจับ Path Traversal
        path_traversal_pattern = re.compile(
            r"(\.\./|\.\.\\)"
        )

        if command_injection_pattern.search(url_path) or command_injection_pattern.search(query_params):
            logger.warning(f"❌ Blocked Malicious Command: {request.client.host} | {request.method} {request.url}")
            raise HTTPException(status_code=400, detail="❌ Malicious command detected in URL")
        
        if path_traversal_pattern.search(url_path) or path_traversal_pattern.search(query_params):
            logger.warning(f"❌ Blocked Path Traversal: {request.client.host} | {request.method} {request.url}")
            raise HTTPException(status_code=400, detail="❌ Path traversal attempt detected in URL")
        
        return await call_next(request)
    
# Middleware สำหรับจัดการ Exception เพื่อให้ Log กระชับ
class ExceptionLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException as http_exc:
            logger.warning(f"🚨 HTTP Exception: {http_exc.status_code} | {request.client.host} | {request.method} {request.url} | {http_exc.detail}")
            raise http_exc
        except Exception as exc:
            logger.error(f"🔥 Unhandled Exception: {request.client.host} | {request.method} {request.url} | {str(exc)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

# ให้บริการไฟล์ static
app.mount("/static", StaticFiles(directory="static"), name="static")


# middleware ต่างๆ
app.add_middleware(BlockMaliciousRequestsMiddleware)
app.add_middleware(ExceptionLoggingMiddleware)
app.add_middleware(FilterInvalidHTTPMethodMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["home.jintaphas.net"])