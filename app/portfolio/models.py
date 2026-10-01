"""Modelos Pydantic compartidos por todo el módulo Portfolio Health."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Position(BaseModel):
    """Posición individual normalizada de una cartera."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    ticker: str
    name: str | None = None
    quantity: float
    currency: str = "USD"
    market_price: float | None = None   # cotización actual (enriquecida)
    avg_cost: float | None = None       # precio promedio de compra (PPC)
    asset_type: str | None = None       # equity | bond | etf | cash | cedear | fci
    sector: str | None = None           # Technology | Energy | etc.
    market_value: float | None = None   # quantity * market_price
    weight: float | None = None         # % sobre el total de la cartera (0–1)


class UploadWarning(BaseModel):
    field: str
    message: str


class UploadResult(BaseModel):
    positions: list[Position]
    warnings: list[UploadWarning] = Field(default_factory=list)
    base_currency: str = "USD"


# ---------------------------------------------------------------------------
# Métricas cuantitativas (Markowitz)
# ---------------------------------------------------------------------------

class PortfolioMetrics(BaseModel):
    volatility_annual: float          # σ_p anualizada
    expected_return_annual: float     # retorno esperado anualizado
    sharpe_ratio: float | None        # (E[r] - r_f) / σ
    avg_pairwise_correlation: float   # correlación promedio entre pares
    most_correlated_pair: list[str]   # [tickerA, tickerB]
    most_correlated_value: float      # coeficiente de correlación del par
    efficient_frontier: list[dict[str, float]]  # [{vol, ret, sharpe}, ...]


# ---------------------------------------------------------------------------
# Health Score
# ---------------------------------------------------------------------------

class HealthScore(BaseModel):
    total: float                   # 0–100 (score final ponderado)
    diversification: float         # sub-score diversificación sectorial
    correlation: float             # sub-score correlación Markowitz
    fx_exposure: float             # sub-score exposición cambiaria
    liquidity: float               # sub-score liquidez
    volatility: float              # sub-score volatilidad


class Risk(BaseModel):
    level: str                     # "red" | "yellow" | "green"
    label: str
    detail: str


class ConcentrationItem(BaseModel):
    sector: str
    weight: float                  # 0–1


class PortfolioHealthReport(BaseModel):
    score: HealthScore
    concentration: list[ConcentrationItem]
    risks: list[Risk]
    metrics: PortfolioMetrics
    narrative: str = ""            # texto generado por LLM (se llena en streaming)
    disclaimer: str = (
        "Este análisis es informativo y no constituye asesoramiento de inversión. "
        "Consultá a un asesor financiero habilitado antes de tomar decisiones."
    )


# ---------------------------------------------------------------------------
# Request / Response de los endpoints
# ---------------------------------------------------------------------------

class AnalysisRequest(BaseModel):
    positions: list[Position]
    language: str = "es"           # "es" | "en"
    base_currency: str = "USD"


class ChatMessage(BaseModel):
    role: str                      # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    report_summary: dict[str, Any] | None = None   # resumen del reporte para contexto
    language: str = "es"
