"""
Parser de archivos de cartera: PDF, Excel (.xlsx/.xls) y CSV.

Flujo:
  1. Detectar formato por tipo MIME / extensión.
  2. Extraer filas candidatas usando la librería específica.
  3. Mapear columnas a la estructura Position normalizada.
  4. Si el PDF no tiene tablas estructuradas, delegar al LLM (Gemini Flash)
     para extraer posiciones de texto libre.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

import pdfplumber
import openpyxl

from app.portfolio.models import Position, UploadResult, UploadWarning

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapa de columnas conocidas → campo normalizado
# ---------------------------------------------------------------------------

_COL_MAP: dict[str, str] = {
    # ticker / instrumento
    "ticker": "ticker",
    "symbol": "ticker",
    "especie": "ticker",
    "instrumento": "ticker",
    "activo": "ticker",
    "asset": "ticker",
    "security": "ticker",
    "código": "ticker",
    "codigo": "ticker",
    # nombre
    "name": "name",
    "nombre": "name",
    "description": "name",
    "descripción": "name",
    "descripcion": "name",
    # cantidad
    "quantity": "quantity",
    "cantidad": "quantity",
    "qty": "quantity",
    "shares": "quantity",
    "unidades": "quantity",
    "nominal": "quantity",
    # precio de mercado
    "price": "market_price",
    "precio": "market_price",
    "market price": "market_price",
    "precio de mercado": "market_price",
    "last price": "market_price",
    "close": "market_price",
    "cierre": "market_price",
    # precio promedio de compra
    "avg cost": "avg_cost",
    "average cost": "avg_cost",
    "ppc": "avg_cost",
    "precio promedio": "avg_cost",
    "costo promedio": "avg_cost",
    "cost basis": "avg_cost",
    "precio promedio de compra": "avg_cost",
    # moneda
    "currency": "currency",
    "moneda": "currency",
    # tipo de activo
    "type": "asset_type",
    "asset type": "asset_type",
    "tipo": "asset_type",
    "tipo de activo": "asset_type",
    "clase": "asset_type",
    # sector
    "sector": "sector",
    "industry": "sector",
    "industria": "sector",
    # valor de mercado
    "market value": "market_value",
    "valor": "market_value",
    "mtm": "market_value",
    "valuación": "market_value",
    "valuation": "market_value",
}


def _normalize_header(header: str) -> str:
    return header.strip().lower().replace("_", " ")


def _map_columns(headers: list[str]) -> dict[int, str]:
    """Devuelve {col_index: campo_normalizado} para las columnas reconocidas."""
    mapping: dict[int, str] = {}
    for i, h in enumerate(headers):
        normalized = _normalize_header(h)
        if normalized in _COL_MAP:
            field = _COL_MAP[normalized]
            if field not in mapping.values():
                mapping[i] = field
    return mapping


def _row_to_position(row: list[Any], col_map: dict[int, str]) -> Position | None:
    """Convierte una fila de datos a Position. Retorna None si no hay ticker."""
    data: dict[str, Any] = {}
    for idx, field in col_map.items():
        if idx < len(row):
            val = row[idx]
            if val is not None and str(val).strip() != "":
                data[field] = str(val).strip()

    ticker = data.get("ticker")
    if not ticker:
        return None
    ticker = ticker.upper().replace(" ", "")

    def _float(key: str) -> float | None:
        try:
            raw = data.get(key)
            if raw is None:
                return None
            return float(str(raw).replace(",", ".").replace("$", "").replace("%", "").strip())
        except (ValueError, TypeError):
            return None

    quantity = _float("quantity")
    if quantity is None or quantity == 0:
        return None

    return Position(
        ticker=ticker,
        name=data.get("name"),
        quantity=quantity,
        currency=(data.get("currency") or "USD").upper().strip(),
        market_price=_float("market_price"),
        avg_cost=_float("avg_cost"),
        asset_type=data.get("asset_type"),
        sector=data.get("sector"),
        market_value=_float("market_value"),
    )


def _normalize_weights(positions: list[Position]) -> list[Position]:
    """Calcula market_value y weight para cada posición."""
    for p in positions:
        if p.market_value is None and p.market_price is not None:
            p.market_value = p.quantity * p.market_price

    total = sum(p.market_value for p in positions if p.market_value is not None)
    if total and total > 0:
        for p in positions:
            if p.market_value is not None:
                p.weight = round(p.market_value / total, 6)
    return positions


def _detect_base_currency(positions: list[Position]) -> str:
    counts: dict[str, int] = {}
    for p in positions:
        counts[p.currency] = counts.get(p.currency, 0) + 1
    return max(counts, key=lambda k: counts[k]) if counts else "USD"


# ---------------------------------------------------------------------------
# Parsers por formato
# ---------------------------------------------------------------------------

def parse_pdf(file_bytes: bytes) -> UploadResult:
    """Extrae posiciones de un PDF usando pdfplumber. Busca tablas estructuradas."""
    warnings: list[UploadWarning] = []
    all_rows: list[list[Any]] = []
    headers: list[str] = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue
                if not headers:
                    # Primera fila con contenido como headers
                    candidate = [str(c or "").strip() for c in table[0]]
                    if any(_normalize_header(c) in _COL_MAP for c in candidate):
                        headers = candidate
                        all_rows.extend(table[1:])
                    else:
                        # Intentar segunda fila como headers
                        if len(table) > 2:
                            candidate2 = [str(c or "").strip() for c in table[1]]
                            if any(_normalize_header(c) in _COL_MAP for c in candidate2):
                                headers = candidate2
                                all_rows.extend(table[2:])
                else:
                    all_rows.extend(table[1:])  # mismo esquema, continuar

    if not headers:
        warnings.append(UploadWarning(
            field="file",
            message=(
                "No se detectaron tablas estructuradas en el PDF. "
                "El análisis con IA intentará extraer las posiciones del texto."
            ),
        ))
        # Intentar texto plano como fallback
        raw_text = _extract_pdf_text(file_bytes)
        return UploadResult(
            positions=[],
            warnings=warnings,
            base_currency="USD",
        )

    col_map = _map_columns(headers)
    if "ticker" not in col_map.values():
        warnings.append(UploadWarning(
            field="ticker",
            message="No se encontró columna de ticker/instrumento. Revisá los encabezados del archivo.",
        ))
        return UploadResult(positions=[], warnings=warnings)

    positions: list[Position] = []
    for row in all_rows:
        pos = _row_to_position(row, col_map)
        if pos:
            positions.append(pos)

    if not positions:
        warnings.append(UploadWarning(
            field="file",
            message="El PDF tiene tablas pero no se pudo extraer ninguna posición válida.",
        ))

    positions = _normalize_weights(positions)
    return UploadResult(
        positions=positions,
        warnings=warnings,
        base_currency=_detect_base_currency(positions),
    )


def _extract_pdf_text(file_bytes: bytes) -> str:
    """Extrae todo el texto de un PDF como string plano."""
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


def parse_excel(file_bytes: bytes) -> UploadResult:
    """Extrae posiciones de un archivo Excel (.xlsx / .xls)."""
    warnings: list[UploadWarning] = []
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)

    # Buscar la hoja con más datos
    target_sheet = wb.active
    if target_sheet is None:
        for name in wb.sheetnames:
            sheet = wb[name]
            if sheet.max_row and sheet.max_row > 1:
                target_sheet = sheet
                break

    if target_sheet is None or target_sheet.max_row is None or target_sheet.max_row < 2:
        warnings.append(UploadWarning(field="file", message="El archivo Excel no contiene datos."))
        return UploadResult(positions=[], warnings=warnings)

    rows = list(target_sheet.iter_rows(values_only=True))
    wb.close()

    # Encontrar la fila de headers (primera que tenga columnas reconocibles)
    header_idx = 0
    headers: list[str] = []
    for i, row in enumerate(rows[:10]):
        candidate = [str(c or "").strip() for c in row]
        if any(_normalize_header(c) in _COL_MAP for c in candidate):
            headers = candidate
            header_idx = i
            break

    if not headers:
        warnings.append(UploadWarning(
            field="file",
            message="No se reconocieron encabezados de columnas. Revisá que el archivo incluya: ticker, cantidad, precio.",
        ))
        return UploadResult(positions=[], warnings=warnings)

    col_map = _map_columns(headers)
    positions: list[Position] = []
    for row in rows[header_idx + 1:]:
        pos = _row_to_position(list(row), col_map)
        if pos:
            positions.append(pos)

    if not positions:
        warnings.append(UploadWarning(
            field="file",
            message="No se encontraron posiciones válidas en el archivo Excel.",
        ))

    positions = _normalize_weights(positions)
    return UploadResult(
        positions=positions,
        warnings=warnings,
        base_currency=_detect_base_currency(positions),
    )


def parse_csv(file_bytes: bytes) -> UploadResult:
    """Extrae posiciones de un archivo CSV (separador auto-detectado)."""
    warnings: list[UploadWarning] = []

    # Intentar decodificar con UTF-8, luego latin-1
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    # Detectar separador
    sample = text[:2048]
    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    reader = csv.reader(io.StringIO(text), dialect=dialect)
    rows = [row for row in reader if any(cell.strip() for cell in row)]

    if len(rows) < 2:
        warnings.append(UploadWarning(field="file", message="El CSV no contiene datos suficientes."))
        return UploadResult(positions=[], warnings=warnings)

    # Detectar fila de headers
    headers: list[str] = []
    header_idx = 0
    for i, row in enumerate(rows[:10]):
        if any(_normalize_header(c) in _COL_MAP for c in row):
            headers = row
            header_idx = i
            break

    if not headers:
        warnings.append(UploadWarning(
            field="file",
            message="No se reconocieron encabezados. Revisá que el CSV tenga: ticker, cantidad, precio.",
        ))
        return UploadResult(positions=[], warnings=warnings)

    col_map = _map_columns(headers)
    positions: list[Position] = []
    for row in rows[header_idx + 1:]:
        pos = _row_to_position(row, col_map)
        if pos:
            positions.append(pos)

    if not positions:
        warnings.append(UploadWarning(
            field="file",
            message="No se encontraron posiciones válidas en el CSV.",
        ))

    positions = _normalize_weights(positions)
    return UploadResult(
        positions=positions,
        warnings=warnings,
        base_currency=_detect_base_currency(positions),
    )


# ---------------------------------------------------------------------------
# Dispatcher principal
# ---------------------------------------------------------------------------

def parse_file(file_bytes: bytes, filename: str) -> UploadResult:
    """Detecta el formato por extensión y delega al parser correspondiente."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        return parse_pdf(file_bytes)
    elif ext in {"xlsx", "xls"}:
        return parse_excel(file_bytes)
    elif ext == "csv":
        return parse_csv(file_bytes)
    else:
        return UploadResult(
            positions=[],
            warnings=[UploadWarning(
                field="file",
                message=f"Formato '{ext}' no soportado. Usá PDF, Excel (.xlsx) o CSV.",
            )],
        )
