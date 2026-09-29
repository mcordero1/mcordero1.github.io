from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.database import ROOT, initialize, make_engine
from app.routes import router


def create_app(database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        engine = make_engine(database_url)
        initialize(engine)
        app.state.engine = engine
        yield
        engine.dispose()

    app = FastAPI(title="Perfil profesional — Marcos Cordero Tenreyro", version="0.1.0", lifespan=lifespan)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.path == "/" or request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'none'"
        return response

    @app.exception_handler(404)
    async def not_found(request, exc):
        return HTMLResponse('<html lang="es"><meta charset="utf-8"><title>Página no encontrada</title><h1>Página no encontrada</h1><a href="/">Volver al perfil</a></html>', status_code=404)

    return app


app = create_app()
