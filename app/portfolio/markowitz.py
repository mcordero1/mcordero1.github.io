"""
Motor de análisis cuantitativo basado en la teoría moderna de portfolios
de Harry Markowitz.

Calcula:
- Matriz de covarianza anualizada
- Volatilidad del portfolio: σ_p = sqrt(w^T Σ w)
- Retorno esperado del portfolio: E[r_p] = w^T μ
- Sharpe Ratio: (E[r_p] - r_f) / σ_p
- Correlación promedio entre pares de activos
- Frontera eficiente por simulación Monte Carlo (5.000 portfolios)
- Contribución marginal de un activo nuevo a la volatilidad
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from app.portfolio.models import PortfolioMetrics

logger = logging.getLogger(__name__)

TRADING_DAYS = 252  # días de trading anuales


def _annualized_cov(returns: pd.DataFrame) -> np.ndarray:
    """Matriz de covarianza anualizada. Excluye columnas con NaN completo."""
    clean = returns.dropna(axis=1, how="all")
    cov = clean.cov().values * TRADING_DAYS
    return cov, list(clean.columns)


def compute_portfolio_metrics(
    tickers: list[str],
    weights: np.ndarray,
    historical_returns: pd.DataFrame,
    risk_free_rate: float = 0.05,
) -> PortfolioMetrics:
    """
    Calcula las métricas cuantitativas completas del portfolio.

    Args:
        tickers: Lista de tickers en el orden correspondiente a weights.
        weights: Vector de pesos (suma = 1).
        historical_returns: DataFrame de retornos diarios.
        risk_free_rate: Tasa libre de riesgo anualizada (decimal).

    Returns:
        PortfolioMetrics con todos los campos calculados.
    """
    # Filtrar a tickers disponibles
    available = [t for t in tickers if t in historical_returns.columns]
    if not available:
        logger.warning("Sin retornos históricos disponibles para calcular métricas Markowitz.")
        return _empty_metrics()

    # Alinear pesos con tickers disponibles
    idx = [tickers.index(t) for t in available]
    w = weights[idx]
    total = w.sum()
    if total == 0:
        return _empty_metrics()
    w = w / total  # re-normalizar si hubo exclusiones

    ret_subset = historical_returns[available].dropna(how="all")

    # Matriz de covarianza anualizada
    cov_matrix = ret_subset.cov().values * TRADING_DAYS

    # Volatilidad del portfolio
    port_variance = float(w @ cov_matrix @ w)
    port_vol = float(np.sqrt(max(port_variance, 0.0)))

    # Retorno esperado anualizado
    mean_daily = ret_subset.mean().values
    port_return = float(w @ mean_daily) * TRADING_DAYS

    # Sharpe Ratio
    sharpe = (
        round((port_return - risk_free_rate) / port_vol, 4)
        if port_vol > 0
        else None
    )

    # Correlación promedio entre pares
    corr_matrix = ret_subset.corr().values
    n = len(available)
    if n > 1:
        upper_triangle = corr_matrix[np.triu_indices(n, k=1)]
        avg_corr = float(np.nanmean(upper_triangle))

        # Par más correlacionado
        max_val = -999.0
        max_i, max_j = 0, 1
        for i in range(n):
            for j in range(i + 1, n):
                v = corr_matrix[i][j]
                if not np.isnan(v) and v > max_val:
                    max_val = v
                    max_i, max_j = i, j
        most_corr_pair = [available[max_i], available[max_j]]
        most_corr_val = round(float(max_val), 4)
    else:
        avg_corr = 0.0
        most_corr_pair = available[:2] if len(available) >= 2 else available + available
        most_corr_val = 0.0

    # Frontera eficiente (Monte Carlo)
    frontier = _simulate_efficient_frontier(ret_subset, n_portfolios=5000, risk_free_rate=risk_free_rate)

    return PortfolioMetrics(
        volatility_annual=round(port_vol, 6),
        expected_return_annual=round(port_return, 6),
        sharpe_ratio=sharpe,
        avg_pairwise_correlation=round(avg_corr, 4),
        most_correlated_pair=most_corr_pair,
        most_correlated_value=most_corr_val,
        efficient_frontier=frontier,
    )


def _simulate_efficient_frontier(
    returns: pd.DataFrame,
    n_portfolios: int = 5000,
    risk_free_rate: float = 0.05,
) -> list[dict[str, float]]:
    """
    Genera puntos de la frontera eficiente por simulación Monte Carlo.
    Retorna los puntos que forman la frontera (máximo retorno para cada vol).
    """
    n = len(returns.columns)
    if n < 2:
        return []

    cov = returns.cov().values * TRADING_DAYS
    mean_ret = returns.mean().values * TRADING_DAYS

    np.random.seed(42)
    all_points: list[dict[str, float]] = []

    for _ in range(n_portfolios):
        raw_w = np.random.random(n)
        w = raw_w / raw_w.sum()
        vol = float(np.sqrt(w @ cov @ w))
        ret = float(w @ mean_ret)
        sharpe = (ret - risk_free_rate) / vol if vol > 0 else 0.0
        all_points.append({"vol": round(vol, 6), "ret": round(ret, 6), "sharpe": round(sharpe, 4)})

    # Calcular frontera eficiente: para cada percentil de volatilidad, el máximo retorno
    if not all_points:
        return []

    vols = [p["vol"] for p in all_points]
    min_vol = min(vols)
    max_vol = max(vols)
    n_bins = 50
    bin_size = (max_vol - min_vol) / n_bins if max_vol > min_vol else 1.0

    frontier: dict[int, dict[str, float]] = {}
    for p in all_points:
        bin_idx = int((p["vol"] - min_vol) / bin_size)
        bin_idx = min(bin_idx, n_bins - 1)
        if bin_idx not in frontier or p["ret"] > frontier[bin_idx]["ret"]:
            frontier[bin_idx] = p

    return sorted(frontier.values(), key=lambda x: x["vol"])


def compute_marginal_contribution(
    new_ticker: str,
    new_weight_pct: float,
    current_tickers: list[str],
    current_weights: np.ndarray,
    historical_returns: pd.DataFrame,
    risk_free_rate: float = 0.05,
) -> dict[str, Any]:
    """
    Calcula cómo cambia la volatilidad del portfolio al agregar un nuevo activo.

    Args:
        new_ticker: Ticker del activo a agregar.
        new_weight_pct: Peso deseado del nuevo activo (0–1).
        current_tickers: Tickers actuales.
        current_weights: Pesos actuales (normalizados).
        historical_returns: DataFrame con retornos históricos (debe incluir new_ticker).
        risk_free_rate: Tasa libre de riesgo.

    Returns:
        Dict con vol_before, vol_after, delta_vol, sharpe_before, sharpe_after.
    """
    # Portfolio actual
    before = compute_portfolio_metrics(
        current_tickers, current_weights, historical_returns, risk_free_rate
    )

    # Reducir pesos actuales proporcionalmente para hacer espacio al nuevo activo
    scale = 1.0 - new_weight_pct
    new_tickers = current_tickers + [new_ticker]
    new_weights = np.append(current_weights * scale, new_weight_pct)

    after = compute_portfolio_metrics(
        new_tickers, new_weights, historical_returns, risk_free_rate
    )

    delta_vol = round(after.volatility_annual - before.volatility_annual, 6)
    delta_pct = round(delta_vol / before.volatility_annual * 100, 2) if before.volatility_annual > 0 else 0.0

    return {
        "vol_before": before.volatility_annual,
        "vol_after": after.volatility_annual,
        "delta_vol": delta_vol,
        "delta_vol_pct": delta_pct,
        "sharpe_before": before.sharpe_ratio,
        "sharpe_after": after.sharpe_ratio,
        "direction": "increase" if delta_vol > 0 else "decrease" if delta_vol < 0 else "neutral",
    }


def _empty_metrics() -> PortfolioMetrics:
    return PortfolioMetrics(
        volatility_annual=0.0,
        expected_return_annual=0.0,
        sharpe_ratio=None,
        avg_pairwise_correlation=0.0,
        most_correlated_pair=[],
        most_correlated_value=0.0,
        efficient_frontier=[],
    )
