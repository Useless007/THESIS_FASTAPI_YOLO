from fastapi import APIRouter,Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates



# เพิ่ม Jinja2 Templates
templates = Jinja2Templates(directory="app/templates")


router = APIRouter(tags=["HTML"])


@router.get("/", response_class=HTMLResponse)
def get_register_form(request: Request):
    """
    แสดง Index HTML
    """
    return templates.TemplateResponse("home.html", {"request": request})
