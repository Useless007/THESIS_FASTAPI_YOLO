# app/main.py

from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from app import middleware
from app.routers import user, product, public, admin, preparation, packing
from fastapi.openapi.utils import get_openapi
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException




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
app.include_router(product.order_router)
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(preparation.router)
# app.include_router(packing.router)

# CORS middleware เพื่อให้ Swagger UI สามารถทำงานได้
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # allow_origins=["https://home.jintaphas.tech"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE","OPTION"],
    allow_headers=["*"],
)


# ให้บริการไฟล์ static
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# middleware ต่างๆ
app.add_middleware(middleware.AuthRedirectMiddleware)
# app.add_middleware(middleware.ExceptionLoggingMiddleware)
# app.add_middleware(middleware.BlockMaliciousRequestsMiddleware)
# app.add_middleware(middleware.FilterInvalidHTTPMethodMiddleware)
# app.add_middleware(TrustedHostMiddleware, allowed_hosts=["home.jintaphas.tech", "thesis-api.jintaphas.tech", "127.0.0.1","192.168.0.44"])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])


# Custom 404 Page
@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return HTMLResponse(f"<h1>Error {exc.status_code}</h1><p>{exc.detail}</p>", status_code=exc.status_code)