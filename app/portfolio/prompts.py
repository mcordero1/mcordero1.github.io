"""
System prompts y plantillas de prompts para el módulo Portfolio Health.

Todos los prompts incluyen los guardrails legales requeridos:
- No emitir recomendaciones expresas de compra/venta/hold.
- Usar lenguaje condicional para proyecciones.
- Redirigir a asesor habilitado ante preguntas directas de inversión.
"""

from __future__ import annotations

from app.portfolio.models import PortfolioHealthReport

DISCLAIMER_ES = (
    "⚠️ *Este análisis es informativo y no constituye asesoramiento de inversión. "
    "Consultá a un asesor financiero habilitado antes de tomar decisiones.*"
)

DISCLAIMER_EN = (
    "⚠️ *This analysis is informational only and does not constitute investment advice. "
    "Consult a licensed financial advisor before making any decisions.*"
)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_ES = """Eres **Portfolio Health**, un asistente especializado en análisis cuantitativo de carteras de inversión.

Tu función es analizar la información provista por el usuario sobre su portfolio y generar diagnósticos objetivos basados en métricas cuantitativas (teoría de Markowitz, diversificación, correlación, volatilidad, Sharpe Ratio).

## RESTRICCIONES ESTRICTAS (guardrails)
- **No emitas recomendaciones expresas de compra, venta o mantenimiento** de ningún activo específico.
- **No hagas pronósticos de precios futuros** con certeza. Usá siempre lenguaje condicional: "podría", "históricamente", "según los datos disponibles", "los modelos sugieren".
- Si el usuario pregunta explícitamente qué debe comprar, vender o hacer con un activo, **explicá el análisis objetivo y recomendá consultar a un asesor financiero habilitado**.
- **No garantices rendimientos** pasados ni futuros.
- Recordá siempre que el análisis es **informativo**, no asesoramiento regulado.

## CAPACIDADES
- Análisis de concentración sectorial y geográfica.
- Interpretación de volatilidad anualizada y su impacto en el perfil de riesgo.
- Correlación entre activos y beneficios de diversificación (Markowitz).
- Exposición cambiaria (ARS/USD/otras monedas).
- Liquidez del portfolio.
- Escenarios hipotéticos: "¿qué pasaría si agrego X?" (análisis de contribución marginal).
- Activos del mercado local argentino (acciones BYMA, bonos soberanos, CEDEARs, FCI) e internacional.
- Interpretación del Portfolio Health Score y sus sub-dimensiones.

## FORMATO DE RESPUESTA
- Respondé en español a menos que el usuario escriba en inglés.
- Usá markdown: negritas para énfasis, listas para enumerar, tablas para comparaciones.
- Sé conciso pero completo. Evitá respuestas de una sola línea para análisis complejos.
- Incluí el disclaimer al final de respuestas que contengan proyecciones o análisis de riesgo.
"""

SYSTEM_PROMPT_EN = """You are **Portfolio Health**, a specialized assistant for quantitative portfolio analysis.

Your role is to analyze the user's portfolio information and generate objective diagnostics based on quantitative metrics (Markowitz theory, diversification, correlation, volatility, Sharpe Ratio).

## STRICT RESTRICTIONS (guardrails)
- **Do not make explicit buy, sell, or hold recommendations** for any specific asset.
- **Do not forecast future prices** with certainty. Always use conditional language: "could", "historically", "according to available data", "models suggest".
- If the user explicitly asks what they should buy, sell, or do with an asset, **explain the objective analysis and recommend consulting a licensed financial advisor**.
- **Do not guarantee past or future returns**.
- Always remember that the analysis is **informational**, not regulated advice.

## CAPABILITIES
- Sectoral and geographic concentration analysis.
- Annualized volatility interpretation and its impact on the risk profile.
- Asset correlation and diversification benefits (Markowitz).
- Currency exposure (ARS/USD/other currencies).
- Portfolio liquidity.
- Hypothetical scenarios: "what if I add X?" (marginal contribution analysis).
- Argentine local market assets (BYMA stocks, sovereign bonds, CEDEARs, mutual funds) and international assets.
- Portfolio Health Score interpretation and its sub-dimensions.

## RESPONSE FORMAT
- Respond in English unless the user writes in Spanish.
- Use markdown: bold for emphasis, lists for enumerations, tables for comparisons.
- Be concise but thorough. Avoid one-line answers for complex analyses.
- Include the disclaimer at the end of responses containing projections or risk analysis.
"""


# ---------------------------------------------------------------------------
# Prompt para generar el reporte narrativo
# ---------------------------------------------------------------------------

def build_analysis_prompt(report: PortfolioHealthReport, language: str = "es") -> str:
    score = report.score
    metrics = report.metrics
    concentration = report.concentration
    risks = report.risks

    level_map = {
        "red": "🔴",
        "yellow": "🟡",
        "green": "🟢",
    }

    concentration_text = "\n".join(
        f"  - {c.sector}: {c.weight*100:.1f}%"
        for c in concentration[:8]
    )

    risks_text = "\n".join(
        f"  {level_map.get(r.level, '⚪')} {r.label}: {r.detail}"
        for r in risks
    )

    if language == "en":
        prompt = f"""Generate a professional portfolio health analysis in English based on the following data:

## Portfolio Health Score: {score.total}/100

### Sub-scores:
- Diversification: {score.diversification}/100
- Correlation (Markowitz): {score.correlation}/100
- Currency exposure: {score.fx_exposure}/100
- Liquidity: {score.liquidity}/100
- Volatility: {score.volatility}/100

### Quantitative metrics:
- Annualized volatility: {metrics.volatility_annual*100:.1f}%
- Expected annual return: {metrics.expected_return_annual*100:.1f}%
- Sharpe Ratio: {metrics.sharpe_ratio if metrics.sharpe_ratio is not None else 'N/A'}
- Average pairwise correlation: {metrics.avg_pairwise_correlation:.2f}
- Most correlated pair: {' / '.join(metrics.most_correlated_pair)} ({metrics.most_correlated_value:.2f})

### Sector concentration:
{concentration_text}

### Detected risks:
{risks_text}

Write a structured narrative analysis (3–5 paragraphs) that:
1. Summarizes the overall portfolio health.
2. Highlights the main strengths.
3. Identifies the most relevant risks.
4. Briefly explains what the metrics mean for the investor's risk profile.
5. Does NOT make explicit buy/sell/hold recommendations.

End with the disclaimer: "{DISCLAIMER_EN}"
"""
    else:
        prompt = f"""Generá un análisis narrativo profesional del estado del portfolio en español, basado en los siguientes datos:

## Portfolio Health Score: {score.total}/100

### Sub-scores:
- Diversificación: {score.diversification}/100
- Correlación (Markowitz): {score.correlation}/100
- Exposición cambiaria: {score.fx_exposure}/100
- Liquidez: {score.liquidity}/100
- Volatilidad: {score.volatility}/100

### Métricas cuantitativas:
- Volatilidad anualizada: {metrics.volatility_annual*100:.1f}%
- Retorno esperado anual: {metrics.expected_return_annual*100:.1f}%
- Sharpe Ratio: {metrics.sharpe_ratio if metrics.sharpe_ratio is not None else 'N/D'}
- Correlación promedio entre activos: {metrics.avg_pairwise_correlation:.2f}
- Par más correlacionado: {' / '.join(metrics.most_correlated_pair)} ({metrics.most_correlated_value:.2f})

### Concentración sectorial:
{concentration_text}

### Riesgos detectados:
{risks_text}

Escribí un análisis narrativo estructurado (3–5 párrafos) que:
1. Resuma el estado general del portfolio.
2. Destaque los principales puntos fuertes.
3. Identifique los riesgos más relevantes.
4. Explique brevemente qué significan las métricas para el perfil de riesgo del inversor.
5. NO haga recomendaciones expresas de compra/venta/hold.

Terminá con el disclaimer: "{DISCLAIMER_ES}"
"""
    return prompt


# ---------------------------------------------------------------------------
# Prompt para el chat de seguimiento
# ---------------------------------------------------------------------------

def build_chat_system_context(report: PortfolioHealthReport, language: str = "es") -> str:
    """Genera el contexto del portfolio para inyectar en el sistema del chat."""
    score = report.score
    metrics = report.metrics
    tickers_str = ", ".join(
        f"{c.sector} ({c.weight*100:.0f}%)"
        for c in report.concentration[:6]
    )

    if language == "en":
        return f"""PORTFOLIO CONTEXT (use this data to answer user questions):
- Health Score: {score.total}/100
- Annualized volatility: {metrics.volatility_annual*100:.1f}%
- Sharpe Ratio: {metrics.sharpe_ratio if metrics.sharpe_ratio is not None else 'N/A'}
- Average correlation: {metrics.avg_pairwise_correlation:.2f}
- Sector distribution: {tickers_str}
- Key risks: {'; '.join(r.label for r in report.risks if r.level == 'red')}
"""
    else:
        return f"""CONTEXTO DEL PORTFOLIO (usá estos datos para responder las preguntas del usuario):
- Health Score: {score.total}/100
- Volatilidad anualizada: {metrics.volatility_annual*100:.1f}%
- Sharpe Ratio: {metrics.sharpe_ratio if metrics.sharpe_ratio is not None else 'N/D'}
- Correlación promedio: {metrics.avg_pairwise_correlation:.2f}
- Distribución sectorial: {tickers_str}
- Riesgos principales: {'; '.join(r.label for r in report.risks if r.level == 'red')}
"""


def build_marginal_contribution_prompt(
    new_ticker: str,
    contribution: dict,
    language: str = "es",
) -> str:
    """Prompt para explicar el impacto de agregar un nuevo activo."""
    direction_es = "aumentaría" if contribution["direction"] == "increase" else "reduciría" if contribution["direction"] == "decrease" else "no cambiaría significativamente"
    direction_en = "would increase" if contribution["direction"] == "increase" else "would decrease" if contribution["direction"] == "decrease" else "would not significantly change"

    if language == "en":
        return f"""The user asks about adding {new_ticker} to their portfolio. Here is the quantitative analysis:

- Current volatility: {contribution['vol_before']*100:.1f}%
- Estimated volatility after adding {new_ticker}: {contribution['vol_after']*100:.1f}%
- Change: {'+' if contribution['delta_vol'] > 0 else ''}{contribution['delta_vol']*100:.1f}% ({contribution['delta_vol_pct']:+.1f}%)
- Current Sharpe Ratio: {contribution['sharpe_before']}
- Estimated Sharpe Ratio after: {contribution['sharpe_after']}

Adding {new_ticker} {direction_en} the portfolio volatility.

Explain this result in 2–3 paragraphs, interpreting what this means for the portfolio's risk profile. Do NOT recommend whether to buy or not."""
    else:
        return f"""El usuario pregunta sobre agregar {new_ticker} a su portfolio. Este es el análisis cuantitativo:

- Volatilidad actual: {contribution['vol_before']*100:.1f}%
- Volatilidad estimada al agregar {new_ticker}: {contribution['vol_after']*100:.1f}%
- Variación: {'+' if contribution['delta_vol'] > 0 else ''}{contribution['delta_vol']*100:.1f}% ({contribution['delta_vol_pct']:+.1f}%)
- Sharpe Ratio actual: {contribution['sharpe_before']}
- Sharpe Ratio estimado post incorporación: {contribution['sharpe_after']}

Incorporar {new_ticker} {direction_es} la volatilidad del portfolio.

Explicá este resultado en 2–3 párrafos, interpretando qué significa para el perfil de riesgo del portfolio. NO recomiendes si comprar o no."""
