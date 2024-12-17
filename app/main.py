# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import user, product , public
from fastapi.openapi.utils import get_openapi
from fastapi.templating import Jinja2Templates

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

# CORS middleware เพื่อให้ Swagger UI สามารถทำงานได้
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)