from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.database import ROOT, read_profile
from app.schemas import Profile
from app.localization import locale_context, localized_profile

router = APIRouter()
templates = Jinja2Templates(directory=ROOT / "templates")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="profile.html", context={"profile": read_profile(request.app.state.engine), **locale_context("es", "/en/")})


@router.get("/en/", response_class=HTMLResponse, include_in_schema=False)
def home_english(request: Request):
    return templates.TemplateResponse(request=request, name="profile.html", context={"profile": localized_profile("en"), **locale_context("en", "/")})


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


@router.get("/health/live", tags=["Estado"])
def liveness():
    # Render consulta esta ruta periódicamente. No despertar PostgreSQL solo
    # para comprobar que el proceso web sigue vivo: consume la cuota gratuita.
    return {"status": "ok"}
