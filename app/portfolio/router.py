"""
Router FastAPI del módulo Portfolio Health.

Endpoints:
  POST /api/v1/portfolio/upload   — parsea el archivo y retorna posiciones detectadas
  POST /api/v1/portfolio/analyze  — análisis completo con SSE streaming
  POST /api/v1/portfolio/chat     — chat de seguimiento con SSE streaming
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.portfolio.llm import get_llm_client, is_llm_available
from app.portfolio.market import get_historical_returns, get_market_data
from app.portfolio.markowitz import compute_marginal_contribution, compute_portfolio_metrics
from app.portfolio.models import (
    AnalysisRequest,
    ChatRequest,
    PortfolioHealthReport,
    Position,
    UploadResult,
)
from app.portfolio.parser import parse_file
from app.portfolio.prompts import (
    DISCLAIMER_ES,
    DISCLAIMER_EN,
    SYSTEM_PROMPT_ES,
    SYSTEM_PROMPT_EN,
    build_analysis_prompt,
    build_chat_system_context,
    build_marginal_contribution_prompt,
)
from app.portfolio.scorer import compute_concentration, compute_health_score, detect_risks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])

# ---------------------------------------------------------------------------
# Rate limiting simple en memoria (por IP)
# ---------------------------------------------------------------------------

_rate_store: dict[str, list[float]] = defaultdict(list)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def _check_rate_limit(ip: str, max_requests: int, window_seconds: int) -> None:
    now = time.time()
    history = _rate_store[ip]
    # Limpiar entradas viejas
    _rate_store[ip] = [t for t in history if now - t < window_seconds]
    if len(_rate_store[ip]) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail="Demasiadas solicitudes. Esperá un momento antes de reintentar.",
        )
    _rate_store[ip].append(now)


def _get_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# Helpers SSE
# ---------------------------------------------------------------------------

def _sse(event: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _sse_text(event: str, text: str) -> str:
    return f"event: {event}\ndata: {json.dumps(text, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# Endpoint 1: Upload
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=UploadResult)
async def upload_portfolio(request: Request, file: UploadFile):
    """
    Recibe el archivo de cartera, lo parsea y retorna las posiciones detectadas.
    No llama al LLM ni a APIs de mercado todavía.
    """
    _check_rate_limit(_get_ip(request), max_requests=20, window_seconds=60)

    # Validar extensión
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in {"pdf", "xlsx", "xls", "csv"}:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado: '{ext}'. Usá PDF, Excel (.xlsx) o CSV.",
        )

    # Leer y validar tamaño
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo supera el límite de {MAX_FILE_SIZE_BYTES // (1024*1024)} MB.",
        )

    result = parse_file(file_bytes, filename)
    return result


# ---------------------------------------------------------------------------
# Endpoint 2: Analyze (SSE streaming)
# ---------------------------------------------------------------------------

@router.post("/analyze")
async def analyze_portfolio(request: Request, body: AnalysisRequest):
    """
    Análisis completo del portfolio con SSE streaming.

    Eventos SSE emitidos:
    - score     → HealthScore (JSON)
    - report    → PortfolioHealthReport sin narrative (JSON)
    - narrative → chunks de texto del LLM
    - done      → señal de fin
    - error     → mensaje de error (si ocurre algo)
    """
    _check_rate_limit(_get_ip(request), max_requests=10, window_seconds=60)

    positions = body.positions
    language = body.language or "es"

    if not positions:
        raise HTTPException(status_code=400, detail="No se recibieron posiciones para analizar.")

    async def event_stream():
        try:
            # 1. Enriquecer posiciones con datos de mercado
            tickers = [p.ticker for p in positions]
            market_data = get_market_data(tickers)

            enriched: list[Position] = []
            for p in positions:
                md = market_data.get(p.ticker)
                if md and md.found:
                    p.market_price = p.market_price or md.price
                    p.sector = p.sector or md.sector
                    p.asset_type = p.asset_type or md.asset_type
                    p.currency = md.currency if md.currency else p.currency
                if p.market_value is None and p.market_price and p.quantity:
                    p.market_value = p.market_price * p.quantity
                enriched.append(p)

            # Recalcular pesos con valores actualizados
            total_val = sum(p.market_value or 0 for p in enriched)
            if total_val > 0:
                for p in enriched:
                    if p.market_value:
                        p.weight = round(p.market_value / total_val, 6)

            # 2. Obtener retornos históricos
            historical = get_historical_returns(tickers, period="1y")

            # 3. Construir vector de pesos para Markowitz
            weights = np.array([p.weight or (1.0 / len(enriched)) for p in enriched])
            weights = weights / weights.sum()

            risk_free = float(os.getenv("RISK_FREE_RATE", "0.05"))

            # 4. Calcular métricas Markowitz
            metrics = compute_portfolio_metrics(
                tickers=tickers,
                weights=weights,
                historical_returns=historical,
                risk_free_rate=risk_free,
            )

            # 5. Concentración y riesgos
            concentration = compute_concentration(enriched)
            score = compute_health_score(enriched, metrics, concentration)
            risks = detect_risks(enriched, metrics, score, concentration)

            # Emitir score primero (actualiza la UI rápido)
            yield _sse("score", score.model_dump())

            # 6. Armar el reporte sin narrative todavía
            report = PortfolioHealthReport(
                score=score,
                concentration=concentration,
                risks=risks,
                metrics=metrics,
            )

            yield _sse("report", json.loads(report.model_dump_json()))

            # 7. Generar narrativa con LLM si está disponible
            if is_llm_available():
                system = SYSTEM_PROMPT_EN if language == "en" else SYSTEM_PROMPT_ES
                user_prompt = build_analysis_prompt(report, language)

                llm = get_llm_client()
                max_tokens = int(os.getenv("AI_MAX_TOKENS_PER_SESSION", "2048"))

                gen = await llm.stream(
                    system_prompt=system,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                )
                async for chunk in gen:
                    yield _sse_text("narrative", chunk)
            else:
                # Sin LLM: emitir un resumen básico basado solo en los datos
                disclaimer = DISCLAIMER_EN if language == "en" else DISCLAIMER_ES
                summary = _build_fallback_narrative(report, language)
                yield _sse_text("narrative", summary + "\n\n" + disclaimer)

            yield _sse("done", {"status": "ok"})

        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Error en analyze_portfolio")
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Endpoint 3: Chat (SSE streaming)
# ---------------------------------------------------------------------------

@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    """
    Chat de seguimiento con contexto del portfolio.
    Streaming SSE con eventos:
    - chunk → fragmento de texto del LLM
    - done  → señal de fin
    """
    _check_rate_limit(_get_ip(request), max_requests=30, window_seconds=60)

    language = body.language or "es"
    user_message = body.message.strip()

    if not user_message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    if not is_llm_available():
        raise HTTPException(
            status_code=503,
            detail="El servicio de IA no está disponible. Configurá GEMINI_API_KEY.",
        )

    async def event_stream():
        try:
            system = SYSTEM_PROMPT_EN if language == "en" else SYSTEM_PROMPT_ES

            # Inyectar contexto del portfolio si está disponible
            if body.report_summary:
                context_note = _build_context_from_summary(body.report_summary, language)
                full_system = system + "\n\n" + context_note
            else:
                full_system = system

            # Detectar si es una pregunta de "¿qué pasa si agrego X?"
            what_if_ticker = _detect_what_if_question(user_message)
            if what_if_ticker and body.report_summary:
                yield _sse_text("chunk", "")  # señal de inicio
                # Calcular contribución marginal
                positions_data = body.report_summary.get("positions", [])
                if positions_data:
                    tickers = [p["ticker"] for p in positions_data if "ticker" in p]
                    weights = np.array([p.get("weight", 1.0 / len(positions_data)) for p in positions_data])
                    weights = weights / weights.sum()
                    historical = get_historical_returns(tickers + [what_if_ticker], period="1y")
                    risk_free = float(os.getenv("RISK_FREE_RATE", "0.05"))
                    contribution = compute_marginal_contribution(
                        new_ticker=what_if_ticker,
                        new_weight_pct=0.05,  # asumir 5% de peso
                        current_tickers=tickers,
                        current_weights=weights,
                        historical_returns=historical,
                        risk_free_rate=risk_free,
                    )
                    user_message_augmented = build_marginal_contribution_prompt(
                        what_if_ticker, contribution, language
                    )
                else:
                    user_message_augmented = user_message
            else:
                user_message_augmented = user_message

            # Convertir historial al formato esperado
            history = [
                {"role": msg.role, "content": msg.content}
                for msg in body.history
            ]

            llm = get_llm_client()
            max_tokens = int(os.getenv("AI_MAX_TOKENS_PER_SESSION", "1024"))

            gen = await llm.chat_stream(
                system_prompt=full_system,
                history=history,
                user_message=user_message_augmented,
                max_tokens=max_tokens,
            )
            async for chunk in gen:
                yield _sse_text("chunk", chunk)

            yield _sse("done", {"status": "ok"})

        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Error en chat endpoint")
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _build_fallback_narrative(report: PortfolioHealthReport, language: str) -> str:
    """Narrativa básica sin LLM, solo con los datos calculados."""
    s = report.score
    v = report.metrics.volatility_annual

    if language == "en":
        return (
            f"**Portfolio Health Score: {s.total}/100**\n\n"
            f"Your portfolio shows the following profile:\n"
            f"- Diversification: {s.diversification}/100\n"
            f"- Correlation: {s.correlation}/100\n"
            f"- Currency exposure: {s.fx_exposure}/100\n"
            f"- Liquidity: {s.liquidity}/100\n"
            f"- Volatility: {s.volatility}/100\n\n"
            f"Estimated annualized volatility: **{v*100:.1f}%**\n"
            f"Sharpe Ratio: **{report.metrics.sharpe_ratio or 'N/A'}**"
        )
    return (
        f"**Portfolio Health Score: {s.total}/100**\n\n"
        f"Tu portfolio presenta el siguiente perfil:\n"
        f"- Diversificación: {s.diversification}/100\n"
        f"- Correlación: {s.correlation}/100\n"
        f"- Exposición cambiaria: {s.fx_exposure}/100\n"
        f"- Liquidez: {s.liquidity}/100\n"
        f"- Volatilidad: {s.volatility}/100\n\n"
        f"Volatilidad anualizada estimada: **{v*100:.1f}%**\n"
        f"Sharpe Ratio: **{report.metrics.sharpe_ratio or 'N/D'}**"
    )


def _build_context_from_summary(summary: dict[str, Any], language: str) -> str:
    """Construye el contexto del portfolio para el system prompt del chat."""
    score = summary.get("score", {})
    metrics = summary.get("metrics", {})
    concentration = summary.get("concentration", [])
    risks = summary.get("risks", [])

    top_sectors = ", ".join(
        f"{c.get('sector', '?')} ({c.get('weight', 0)*100:.0f}%)"
        for c in concentration[:5]
    )
    red_risks = "; ".join(r.get("label", "") for r in risks if r.get("level") == "red")

    if language == "en":
        return (
            f"PORTFOLIO CONTEXT:\n"
            f"- Health Score: {score.get('total', 'N/A')}/100\n"
            f"- Volatility: {(metrics.get('volatility_annual', 0) or 0)*100:.1f}%\n"
            f"- Sharpe Ratio: {metrics.get('sharpe_ratio', 'N/A')}\n"
            f"- Avg correlation: {metrics.get('avg_pairwise_correlation', 'N/A')}\n"
            f"- Sector distribution: {top_sectors}\n"
            f"- Critical risks: {red_risks or 'None'}"
        )
    return (
        f"CONTEXTO DEL PORTFOLIO:\n"
        f"- Health Score: {score.get('total', 'N/D')}/100\n"
        f"- Volatilidad: {(metrics.get('volatility_annual', 0) or 0)*100:.1f}%\n"
        f"- Sharpe Ratio: {metrics.get('sharpe_ratio', 'N/D')}\n"
        f"- Correlación promedio: {metrics.get('avg_pairwise_correlation', 'N/D')}\n"
        f"- Distribución sectorial: {top_sectors}\n"
        f"- Riesgos críticos: {red_risks or 'Ninguno'}"
    )


_WHAT_IF_KEYWORDS_ES = ["agregar", "incorporar", "sumar", "añadir", "comprar", "meter"]
_WHAT_IF_KEYWORDS_EN = ["add", "include", "buy", "incorporate", "what if"]


def _detect_what_if_question(message: str) -> str | None:
    """
    Detecta si el mensaje es una pregunta de "¿qué pasa si agrego X?".
    Retorna el ticker mencionado o None.
    """
    msg_lower = message.lower()
    has_keyword = any(kw in msg_lower for kw in _WHAT_IF_KEYWORDS_ES + _WHAT_IF_KEYWORDS_EN)
    if not has_keyword:
        return None

    # Buscar palabras en mayúsculas (probable ticker)
    import re
    matches = re.findall(r"\b([A-Z]{2,6})\b", message)
    if matches:
        return matches[0]
    return None
