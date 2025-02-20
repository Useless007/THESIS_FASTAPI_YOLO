# app/middleware.py

from fastapi import Request,HTTPException
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
import re,logging

# ตั้งค่า Logger
logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)

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
            raise HTTPException(status_code=500, detail=str(exc))

class AuthRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if response.status_code == 404:
            # ตรวจสอบว่าหน้าปัจจุบันไม่ใช่ /page_not_found ก่อนจะ redirect
            if request.url.path != "/page_not_found":
                print(f"🔄 Redirecting to /page_not_found due to 404: {request.url.path}")
                return RedirectResponse(url="/page_not_found", status_code=302)
        
        return response