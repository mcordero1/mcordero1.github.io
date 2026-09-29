from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.database import ROOT, read_profile
from app.schemas import Profile

router = APIRouter()
templates = Jinja2Templates(directory=ROOT / "templates")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="profile.html", context={"profile": read_profile(request.app.state.engine)})


@router.get("/api/v1/profile", response_model=Profile, tags=["Perfil"])
def profile(request: Request):
    return read_profile(request.app.state.engine)


@router.get("/health", tags=["Estado"])
def health(request: Request):
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)
