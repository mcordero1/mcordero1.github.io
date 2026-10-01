"""
Servicio de datos de mercado.

Obtiene cotizaciones actuales, metadatos (sector, tipo de activo) y
retornos históricos usando yfinance como fuente principal.

Incluye:
- Resolución de tickers locales argentinos al sufijo .BA de Yahoo Finance.
- Caché en memoria por proceso (útil para múltiples llamadas en la misma sesión).
- Fallback gracioso: si un ticker no se resuelve, se retorna con campos None.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapa de tickers locales argentinos → sufijo Yahoo Finance
# ---------------------------------------------------------------------------

_LOCAL_TICKER_MAP: dict[str, str] = {
    # Acciones locales BYMA
    "YPFD": "YPFD.BA",
    "GGAL": "GGAL.BA",
    "BMA": "BMA.BA",
    "PAMP": "PAMP.BA",
    "TECO2": "TECO2.BA",
    "TXAR": "TXAR.BA",
    "ALUA": "ALUA.BA",
    "CRES": "CRES.BA",
    "MIRG": "MIRG.BA",
    "SUPV": "SUPV.BA",
    "CEPU": "CEPU.BA",
    "TRAN": "TRAN.BA",
    "VALO": "VALO.BA",
    "AGRO": "AGRO.BA",
    "BYMA": "BYMA.BA",
    # Bonos soberanos argentinos — sin cobertura en yfinance, mapear a placeholder
    "AL30": None,
    "AL35": None,
    "GD30": None,
    "GD35": None,
    "GD38": None,
    "GD41": None,
    "GD46": None,
    "AL29": None,
    "AE38": None,
    # Letras
    "LEDES": None,
    "LECAP": None,
    # Bonos CER
    "TX26": None,
    "TX28": None,
    "DICP": None,
    # CEDEARs comunes (usan el ticker base en USD)
    "CEDEAR AAPL": "AAPL",
    "CEDEAR GOOGL": "GOOGL",
    "CEDEAR AMZN": "AMZN",
    "CEDEAR MSFT": "MSFT",
    "CEDEAR TSLA": "TSLA",
    "CEDEAR NVDA": "NVDA",
    "CEDEAR MELI": "MELI",
    "CEDEAR GLOB": "GLOB",
    "CEDEAR BABA": "BABA",
    "CEDEAR SPY": "SPY",
    "CEDEAR QQQ": "QQQ",
}


def resolve_ticker(ticker: str) -> str | None:
    """
    Resuelve un ticker local al equivalente de Yahoo Finance.
    Retorna None si el activo no tiene cobertura en yfinance.
    Si el ticker ya está en formato Yahoo Finance (ej. AAPL, SPY), lo devuelve tal cual.
    """
    upper = ticker.upper().strip()

    # Verificar mapa explícito
    if upper in _LOCAL_TICKER_MAP:
        return _LOCAL_TICKER_MAP[upper]

    # Tickers con prefijo CEDEAR
    if upper.startswith("CEDEAR "):
        base = upper.replace("CEDEAR ", "").strip()
        return base

    # Tickers locales que terminan en "D" (dólares en BYMA, ej. YPFD)
    if upper.endswith("D") and len(upper) > 2:
        without_d = upper[:-1]
        yf_candidate = without_d + ".BA"
        return yf_candidate

    # Asumir ticker internacional si no está en el mapa
    return upper


# ---------------------------------------------------------------------------
# Estructuras de datos del servicio
# ---------------------------------------------------------------------------

class MarketData:
    __slots__ = ("ticker", "yf_ticker", "price", "daily_change_pct",
                 "sector", "industry", "asset_type", "currency", "found")

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.yf_ticker: str | None = None
        self.price: float | None = None
        self.daily_change_pct: float | None = None
        self.sector: str | None = None
        self.industry: str | None = None
        self.asset_type: str | None = None
        self.currency: str = "USD"
        self.found: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "yf_ticker": self.yf_ticker,
            "price": self.price,
            "daily_change_pct": self.daily_change_pct,
            "sector": self.sector,
            "industry": self.industry,
            "asset_type": self.asset_type,
            "currency": self.currency,
            "found": self.found,
        }


def _classify_asset_type(info: dict[str, Any], ticker: str) -> str:
    """Clasifica el tipo de activo a partir de la info de yfinance."""
    qt = (info.get("quoteType") or "").upper()
    if qt == "ETF":
        return "etf"
    if qt == "EQUITY":
        # Detectar CEDEAR por sufijo
        if ticker.endswith(".BA"):
            return "equity_local"
        return "equity"
    if qt in {"BOND", "FUTURE", "MUTUALFUND"}:
        return "bond" if qt == "BOND" else qt.lower()
    if qt == "CRYPTOCURRENCY":
        return "crypto"
    if qt == "CURRENCY":
        return "fx"
    return "equity"  # default


def get_market_data(tickers: list[str]) -> dict[str, MarketData]:
    """
    Obtiene cotización y metadatos para una lista de tickers.
    Cachea resultados a nivel de llamada para reducir requests.
    """
    result: dict[str, MarketData] = {}

    for raw_ticker in tickers:
        md = MarketData(raw_ticker)
        yf_ticker = resolve_ticker(raw_ticker)
        md.yf_ticker = yf_ticker

        if yf_ticker is None:
            # Activo local sin cobertura en yfinance (ej. bonos soberanos ARS)
            logger.info("Sin cobertura yfinance para %s", raw_ticker)
            result[raw_ticker] = md
            continue

        try:
            t = yf.Ticker(yf_ticker)
            info = t.info or {}

            price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")

            md.price = float(price) if price else None
            md.daily_change_pct = (
                round((float(price) - float(prev_close)) / float(prev_close) * 100, 2)
                if price and prev_close and float(prev_close) != 0
                else None
            )
            md.sector = info.get("sector")
            md.industry = info.get("industry")
            md.currency = (info.get("currency") or "USD").upper()
            md.asset_type = _classify_asset_type(info, yf_ticker)
            md.found = md.price is not None

        except Exception as exc:
            logger.warning("Error obteniendo datos de mercado para %s (%s): %s", raw_ticker, yf_ticker, exc)

        result[raw_ticker] = md

    return result


def get_historical_returns(
    tickers: list[str],
    period: str = "1y",
) -> pd.DataFrame:
    """
    Retorna un DataFrame de retornos diarios (columnas=tickers, índice=fechas).
    Los tickers sin datos quedan como columnas NaN.
    """
    # Resolver tickers a nombres yfinance y filtrar los que tienen cobertura
    yf_map: dict[str, str] = {}
    for t in tickers:
        resolved = resolve_ticker(t)
        if resolved is not None:
            yf_map[t] = resolved

    if not yf_map:
        return pd.DataFrame()

    yf_tickers = list(yf_map.values())

    try:
        raw = yf.download(
            yf_tickers,
            period=period,
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as exc:
        logger.error("Error descargando histórico: %s", exc)
        return pd.DataFrame()

    # yfinance devuelve MultiIndex cuando hay más de un ticker
    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"]
    else:
        if len(yf_tickers) == 1:
            prices = raw[["Close"]].rename(columns={"Close": yf_tickers[0]})
        else:
            prices = raw

    # Calcular retornos porcentuales diarios
    returns = prices.pct_change().dropna(how="all")

    # Renombrar columnas de yf_ticker → ticker original
    reverse_map = {v: k for k, v in yf_map.items()}
    returns = returns.rename(columns=reverse_map)

    # Agregar columnas NaN para tickers sin cobertura
    for t in tickers:
        if t not in returns.columns:
            returns[t] = float("nan")

    return returns[tickers]  # mantener orden original
