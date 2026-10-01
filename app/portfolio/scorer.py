"""
Lógica del Portfolio Health Score.

El score final (0–100) es la ponderación de 5 dimensiones:
  - Diversificación sectorial  25%
  - Correlación (Markowitz)    20%
  - Exposición cambiaria       15%
  - Liquidez                   15%
  - Volatilidad                25%

Cada sub-score tiene un semáforo:
  🔴 < 40   (riesgo alto)
  🟡 40–69  (atención)
  🟢 ≥ 70   (saludable)
"""

from __future__ import annotations

import logging
from collections import defaultdict

from app.portfolio.models import (
    ConcentrationItem,
    HealthScore,
    PortfolioMetrics,
    Position,
    Risk,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Activos de alta liquidez conocidos
# ---------------------------------------------------------------------------

_HIGH_LIQUIDITY_TICKERS = {
    "SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "TLT", "IEF", "LQD",
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "BRK.B",
    "JPM", "BAC", "GS", "MS", "XOM", "CVX",
    "BTC", "ETH",
}

_HIGH_LIQUIDITY_ASSET_TYPES = {"etf", "equity"}

# ---------------------------------------------------------------------------
# Sub-scores
# ---------------------------------------------------------------------------


def score_diversification(concentration_by_sector: list[ConcentrationItem]) -> float:
    """
    Penaliza la concentración sectorial.
    - max_sector_weight <= 0.20: score 100
    - 0.20–0.40: penalización lineal hasta 70
    - 0.40–0.60: penalización lineal hasta 40
    - > 0.60: score < 40, mínimo 0
    """
    if not concentration_by_sector:
        return 50.0

    max_w = max(item.weight for item in concentration_by_sector)
    n_sectors = len(concentration_by_sector)

    # Bonificar diversificación entre muchos sectores
    sector_bonus = min(n_sectors * 2, 10)

    if max_w <= 0.20:
        base = 100.0
    elif max_w <= 0.40:
        base = 100.0 - ((max_w - 0.20) / 0.20) * 30.0
    elif max_w <= 0.60:
        base = 70.0 - ((max_w - 0.40) / 0.20) * 30.0
    elif max_w <= 0.80:
        base = 40.0 - ((max_w - 0.60) / 0.20) * 30.0
    else:
        base = max(0.0, 10.0 - (max_w - 0.80) * 50.0)

    return min(100.0, round(base + sector_bonus, 2))


def score_correlation(avg_pairwise_correlation: float) -> float:
    """
    Penaliza alta correlación promedio entre activos.
    - corr <= 0.3: score 100
    - 0.3–0.6: penalización lineal hasta 70
    - 0.6–0.8: penalización lineal hasta 40
    - > 0.8: score < 40
    """
    c = avg_pairwise_correlation
    if c <= 0.30:
        return 100.0
    elif c <= 0.60:
        return round(100.0 - ((c - 0.30) / 0.30) * 30.0, 2)
    elif c <= 0.80:
        return round(70.0 - ((c - 0.60) / 0.20) * 30.0, 2)
    elif c <= 0.90:
        return round(40.0 - ((c - 0.80) / 0.10) * 30.0, 2)
    else:
        return max(0.0, round(10.0 - (c - 0.90) * 100.0, 2))


def score_fx_exposure(currency_breakdown: dict[str, float]) -> float:
    """
    Evalúa el balance de exposición cambiaria.
    - Cartera 100% en una sola moneda: score 60 (no es pésimo, pero se puede diversificar)
    - Diversificación ARS/USD: score más alto
    - Más de 3 monedas: score 90+
    """
    if not currency_breakdown:
        return 50.0

    total = sum(currency_breakdown.values())
    if total == 0:
        return 50.0

    weights = {k: v / total for k, v in currency_breakdown.items()}
    n_currencies = len(weights)
    max_weight = max(weights.values())

    if n_currencies == 1:
        return 60.0
    elif n_currencies == 2:
        # Mejor si la más grande no supera 80%
        if max_weight <= 0.60:
            return 90.0
        elif max_weight <= 0.80:
            return 75.0
        else:
            return 65.0
    elif n_currencies == 3:
        return 92.0
    else:
        return 98.0


def score_liquidity(positions: list[Position]) -> float:
    """
    Evalúa la proporción del portfolio en activos de alta liquidez.
    - >= 80% en activos líquidos: score 100
    - 60–80%: score 80
    - 40–60%: score 60
    - < 40%: score 40
    """
    if not positions:
        return 50.0

    total_value = sum(p.market_value or 0 for p in positions)
    if total_value == 0:
        # Fallback por cantidad de posiciones líquidas
        n_liquid = sum(
            1 for p in positions
            if p.ticker.upper() in _HIGH_LIQUIDITY_TICKERS
            or (p.asset_type or "") in _HIGH_LIQUIDITY_ASSET_TYPES
        )
        liquid_ratio = n_liquid / len(positions) if positions else 0
    else:
        liquid_value = sum(
            (p.market_value or 0) for p in positions
            if p.ticker.upper() in _HIGH_LIQUIDITY_TICKERS
            or (p.asset_type or "") in _HIGH_LIQUIDITY_ASSET_TYPES
        )
        liquid_ratio = liquid_value / total_value

    if liquid_ratio >= 0.80:
        return 100.0
    elif liquid_ratio >= 0.60:
        return 80.0
    elif liquid_ratio >= 0.40:
        return 60.0
    elif liquid_ratio >= 0.20:
        return 40.0
    else:
        return 20.0


def score_volatility(annual_vol: float) -> float:
    """
    Convierte la volatilidad anualizada en un score.
    - < 8%:    100  (baja volatilidad, muy conservador)
    - 8–15%:   90–70 (moderado)
    - 15–25%:  70–40 (moderado-agresivo)
    - 25–40%:  40–20 (agresivo)
    - > 40%:   < 20  (muy agresivo)
    """
    v = annual_vol
    if v <= 0.0:
        return 50.0  # sin datos, neutral
    elif v <= 0.08:
        return 100.0
    elif v <= 0.15:
        return round(100.0 - ((v - 0.08) / 0.07) * 20.0, 2)
    elif v <= 0.25:
        return round(80.0 - ((v - 0.15) / 0.10) * 30.0, 2)
    elif v <= 0.40:
        return round(50.0 - ((v - 0.25) / 0.15) * 20.0, 2)
    else:
        return max(0.0, round(30.0 - (v - 0.40) * 50.0, 2))


# ---------------------------------------------------------------------------
# Score final
# ---------------------------------------------------------------------------

WEIGHTS = {
    "diversification": 0.25,
    "correlation": 0.20,
    "fx_exposure": 0.15,
    "liquidity": 0.15,
    "volatility": 0.25,
}


def compute_health_score(
    positions: list[Position],
    metrics: PortfolioMetrics,
    concentration: list[ConcentrationItem],
) -> HealthScore:
    """Calcula el Portfolio Health Score completo."""
    # Distribución por moneda
    currency_breakdown: dict[str, float] = defaultdict(float)
    for p in positions:
        currency_breakdown[p.currency] += p.market_value or p.quantity

    s_div = score_diversification(concentration)
    s_cor = score_correlation(metrics.avg_pairwise_correlation)
    s_fx = score_fx_exposure(dict(currency_breakdown))
    s_liq = score_liquidity(positions)
    s_vol = score_volatility(metrics.volatility_annual)

    total = round(
        WEIGHTS["diversification"] * s_div
        + WEIGHTS["correlation"] * s_cor
        + WEIGHTS["fx_exposure"] * s_fx
        + WEIGHTS["liquidity"] * s_liq
        + WEIGHTS["volatility"] * s_vol,
        1,
    )

    return HealthScore(
        total=total,
        diversification=round(s_div, 1),
        correlation=round(s_cor, 1),
        fx_exposure=round(s_fx, 1),
        liquidity=round(s_liq, 1),
        volatility=round(s_vol, 1),
    )


# ---------------------------------------------------------------------------
# Concentración sectorial
# ---------------------------------------------------------------------------

_DEFAULT_SECTOR = "Sin clasificar"

_ASSET_TYPE_TO_SECTOR = {
    "bond": "Renta Fija",
    "cash": "Cash",
    "fci": "Fondos",
    "crypto": "Criptoactivos",
    "fx": "Divisas",
}


def compute_concentration(positions: list[Position]) -> list[ConcentrationItem]:
    """Calcula la concentración por sector."""
    sector_values: dict[str, float] = defaultdict(float)
    total = 0.0

    for p in positions:
        # Determinar sector
        if p.sector:
            sector = p.sector
        elif p.asset_type and p.asset_type in _ASSET_TYPE_TO_SECTOR:
            sector = _ASSET_TYPE_TO_SECTOR[p.asset_type]
        else:
            sector = _DEFAULT_SECTOR

        value = p.market_value or p.quantity
        sector_values[sector] += value
        total += value

    if total == 0:
        return []

    items = [
        ConcentrationItem(sector=s, weight=round(v / total, 4))
        for s, v in sector_values.items()
    ]
    return sorted(items, key=lambda x: x.weight, reverse=True)


# ---------------------------------------------------------------------------
# Detección de riesgos
# ---------------------------------------------------------------------------

def _level(score: float) -> str:
    if score < 40:
        return "red"
    elif score < 70:
        return "yellow"
    return "green"


def detect_risks(
    positions: list[Position],
    metrics: PortfolioMetrics,
    score: HealthScore,
    concentration: list[ConcentrationItem],
) -> list[Risk]:
    """Genera la lista de riesgos detectados con nivel y descripción."""
    risks: list[Risk] = []

    # Concentración sectorial
    if concentration:
        top = concentration[0]
        if top.weight > 0.40:
            risks.append(Risk(
                level="red",
                label="Alta concentración sectorial",
                detail=f"{top.sector} representa el {top.weight*100:.0f}% del portfolio.",
            ))
        elif top.weight > 0.25:
            risks.append(Risk(
                level="yellow",
                label="Concentración sectorial moderada",
                detail=f"{top.sector} representa el {top.weight*100:.0f}% del portfolio.",
            ))
        else:
            risks.append(Risk(
                level="green",
                label="Diversificación sectorial adecuada",
                detail=f"Ningún sector supera el {top.weight*100:.0f}% del portfolio.",
            ))

    # Correlación entre activos
    corr = metrics.avg_pairwise_correlation
    if corr > 0.80:
        risks.append(Risk(
            level="red",
            label="Alta correlación entre posiciones",
            detail=f"Correlación promedio: {corr:.2f}. El par más correlacionado es "
                   f"{' / '.join(metrics.most_correlated_pair)} ({metrics.most_correlated_value:.2f}).",
        ))
    elif corr > 0.60:
        risks.append(Risk(
            level="yellow",
            label="Correlación moderada entre posiciones",
            detail=f"Correlación promedio: {corr:.2f}. Diversificar en activos menos correlacionados podría reducir el riesgo.",
        ))
    else:
        risks.append(Risk(
            level="green",
            label="Baja correlación entre posiciones",
            detail=f"Correlación promedio: {corr:.2f}. Buena diversificación.",
        ))

    # Exposición cambiaria
    if score.fx_exposure < 40:
        risks.append(Risk(
            level="red",
            label="Exposición cambiaria concentrada",
            detail="El portfolio está expuesto a una única moneda. Considerar diversificación en USD/ARS u otras.",
        ))
    elif score.fx_exposure < 70:
        risks.append(Risk(
            level="yellow",
            label="Exposición cambiaria moderada",
            detail="Cierta diversificación de monedas, pero con concentración significativa en una.",
        ))
    else:
        risks.append(Risk(
            level="green",
            label="Exposición cambiaria diversificada",
            detail="El portfolio tiene buena distribución de monedas.",
        ))

    # Liquidez
    if score.liquidity < 40:
        risks.append(Risk(
            level="red",
            label="Liquidez baja",
            detail="Una proporción significativa del portfolio está en activos de baja liquidez.",
        ))
    elif score.liquidity < 70:
        risks.append(Risk(
            level="yellow",
            label="Liquidez moderada",
            detail="Liquidez aceptable, pero puede haber dificultades para salir de algunas posiciones rápidamente.",
        ))
    else:
        risks.append(Risk(
            level="green",
            label="Liquidez adecuada",
            detail="La mayoría del portfolio está en activos de alta liquidez.",
        ))

    # Volatilidad
    vol = metrics.volatility_annual
    if vol > 0.35:
        risks.append(Risk(
            level="red",
            label="Volatilidad muy alta",
            detail=f"Volatilidad anualizada estimada: {vol*100:.1f}%. Portfolio con perfil muy agresivo.",
        ))
    elif vol > 0.20:
        risks.append(Risk(
            level="yellow",
            label="Volatilidad elevada",
            detail=f"Volatilidad anualizada estimada: {vol*100:.1f}%. Perfil moderado-agresivo.",
        ))
    elif vol > 0.0:
        risks.append(Risk(
            level="green",
            label="Volatilidad controlada",
            detail=f"Volatilidad anualizada estimada: {vol*100:.1f}%.",
        ))

    # Posiciones muy concentradas individualmente
    for p in positions:
        if p.weight and p.weight > 0.25:
            risks.append(Risk(
                level="yellow",
                label=f"Alta concentración en {p.ticker}",
                detail=f"{p.ticker} representa el {p.weight*100:.0f}% del portfolio.",
            ))

    return risks
