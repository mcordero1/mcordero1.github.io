"""
Parser de archivos de cartera: PDF, Excel (.xlsx/.xls) y CSV.

Flujo:
  1. Detectar formato por tipo MIME / extensión.
  2. Extraer filas candidatas usando la librería específica.
  3. Mapear columnas a la estructura Position normalizada.
  4. Para PDFs con secciones separadas (ej. Centaurus), parsear cada
     sección individualmente acumulando posiciones.
"""

from __future__ import annotations

import csv
import io
import logging
import re
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
    "símbolo": "ticker",
    "simbolo": "ticker",
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
    "denominación": "name",
    "denominacion": "name",
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
    "total tenencia": "quantity",
    # precio de mercado
    "price": "market_price",
    "precio": "market_price",
    "cotización": "market_price",
    "cotizacion": "market_price",
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
    "importe": "market_value",
    "mtm": "market_value",
    "valuación": "market_value",
    "valuation": "market_value",
}

# Secciones del PDF de Centaurus y su tipo de activo
_SECTION_ASSET_TYPES: dict[str, str] = {
    "acciones": "equity",
    "obligaciones negociables": "bond",
    "títulos públicos": "bond",
    "titulos publicos": "bond",
    "fondos": "fci",
    "fci": "fci",
    "cedears": "cedear",
    "letras": "bond",
    "bonos": "bond",
    "liquidez": "cash",
    "saldos monetarios": "cash",
}

# Filas a ignorar en el PDF de Centaurus (subtotales, monedas, etc.)
_SKIP_ROW_PATTERNS = re.compile(
    r"^(total|subtotal|pesos arg|dólar|dolar|dollar|subtotales|hoja|"
    r"ars|usd|usdc|usdm|cuenta comitente|denominación|símbolo|simbolo|"
    r"tenencia|valuación|fecha|tipo de cambio|% s/activo)$",
    re.IGNORECASE,
)


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


def _clean_number(raw: str) -> float | None:
    """Convierte strings numéricos con formato argentino/internacional a float."""
    if not raw:
        return None
    # Quitar símbolos de moneda y espacios
    cleaned = raw.replace("$", "").replace("U$S", "").replace("U$S C", "").strip()
    cleaned = cleaned.replace("%", "").strip()
    # Formato argentino: 1.234.567,89 → 1234567.89
    # Formato argentino sin decimales: 1.360 → 1360 (punto como separador de miles)
    if "," in cleaned and "." in cleaned:
        # Si la coma viene después del punto: es decimal argentino (1.234,56)
        if cleaned.rindex(",") > cleaned.rindex("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        # Solo coma: puede ser decimal (1,5) o miles (1,360) — asumir decimal
        cleaned = cleaned.replace(",", ".")
    elif "." in cleaned:
        # Solo punto: puede ser miles (1.360) o decimal (1.5)
        # Si hay exactamente 3 dígitos después del punto, es separador de miles
        parts = cleaned.split(".")
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            cleaned = cleaned.replace(".", "")
        # Si hay múltiples puntos, todos son separadores de miles
        elif len(parts) > 2:
            cleaned = cleaned.replace(".", "")
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _row_to_position(
    row: list[Any],
    col_map: dict[int, str],
    default_asset_type: str | None = None,
    default_currency: str | None = None,
) -> Position | None:
    """Convierte una fila de datos a Position. Retorna None si no hay ticker válido."""
    data: dict[str, Any] = {}
    for idx, field in col_map.items():
        if idx < len(row):
            val = row[idx]
            if val is not None and str(val).strip() not in ("", "—", "-"):
                data[field] = str(val).strip()

    ticker = data.get("ticker")
    if not ticker:
        return None

    # Limpiar ticker
    ticker = ticker.upper().strip()
    # Ignorar filas que son subtotales o headers repetidos
    if _SKIP_ROW_PATTERNS.match(ticker):
        return None
    # Ignorar tickers muy largos (probablemente texto de descripción)
    if len(ticker) > 15:
        return None

    ticker = ticker.replace(" ", "")

    quantity = _clean_number(data.get("quantity", ""))
    if quantity is None or quantity == 0:
        return None

    # Detectar moneda: del campo moneda o del default de la sección
    raw_currency = data.get("currency") or default_currency or "USD"
    currency = raw_currency.upper().strip()
    # Normalizar monedas del mercado local
    currency_map = {
        "ARS": "ARS", "PESOS": "ARS", "$": "ARS",
        "USD": "USD", "USDC": "USD", "USDM": "USD",
        "U$S": "USD", "U$S C": "USD",
    }
    currency = currency_map.get(currency, currency)

    market_price = _clean_number(data.get("market_price", ""))
    market_value = _clean_number(data.get("market_value", ""))
    avg_cost = _clean_number(data.get("avg_cost", ""))

    return Position(
        ticker=ticker,
        name=data.get("name"),
        quantity=quantity,
        currency=currency,
        market_price=market_price,
        avg_cost=avg_cost,
        asset_type=default_asset_type or data.get("asset_type"),
        sector=data.get("sector"),
        market_value=market_value,
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


def _is_header_row(row: list[Any]) -> bool:
    """Detecta si una fila es una fila de headers (contiene columnas conocidas)."""
    cells = [str(c or "").strip().lower() for c in row]
    matches = sum(1 for c in cells if c in _COL_MAP)
    return matches >= 2


def _detect_section_type(text: str) -> str | None:
    """Detecta el tipo de activo a partir del texto de una sección."""
    text_lower = text.lower().strip()
    for key, asset_type in _SECTION_ASSET_TYPES.items():
        if key in text_lower:
            return asset_type
    return None


# ---------------------------------------------------------------------------
# Parser PDF — estrategia multi-sección
# ---------------------------------------------------------------------------

async def parse_pdf(file_bytes: bytes) -> UploadResult:
    """
    Extrae posiciones de un PDF usando pdfplumber.

    Estrategia adaptada al formato real de los PDFs de brokers argentinos
    (Centaurus y similares), donde pdfplumber extrae cada fila como una
    sola celda de texto en lugar de columnas separadas.

    Orden de intentos:
    1. Parseo por texto con regex (formato Centaurus/brokers AR).
    2. Tabla estructurada con columnas separadas (brokers internacionales).
    3. Mensaje de error con sugerencia de usar CSV/Excel.
    """
    warnings: list[UploadWarning] = []

    # Extraer todo el texto del PDF
    full_text = _extract_pdf_text(file_bytes)

    if not full_text.strip():
        warnings.append(UploadWarning(
            field="file",
            message="No se pudo extraer texto del PDF. El archivo puede estar escaneado o protegido.",
        ))
        return UploadResult(positions=[], warnings=warnings, base_currency="USD")

    # Estrategia 1: parseo por texto (funciona con Centaurus y brokers AR)
    positions = _parse_pdf_by_text(full_text)

    # Estrategia 2: tablas con columnas separadas (brokers internacionales)
    if not positions:
        positions = _parse_pdf_by_tables(file_bytes)

    # Estrategia 3: fallback a Gemini Flash si las dos anteriores fallaron
    if not positions:
        logger.info("Intentando parseo de PDF con Gemini Flash...")
        from app.portfolio.llm import parse_pdf_with_llm
        raw_dicts = await parse_pdf_with_llm(full_text)
        positions = _dict_list_to_positions(raw_dicts)
        if positions:
            warnings.append(UploadWarning(
                field="file",
                message=(
                    "Las posiciones fueron extraídas mediante IA "
                    "(el formato del PDF no es estándar). "
                    "Verificá que los datos sean correctos antes de analizar."
                ),
            ))

    if not positions:
        warnings.append(UploadWarning(
            field="file",
            message=(
                "No se pudieron extraer posiciones del PDF. "
                "Intentá exportar desde tu broker como CSV o Excel para mejor compatibilidad."
            ),
        ))
        return UploadResult(positions=[], warnings=warnings, base_currency="USD")

    positions = _normalize_weights(positions)
    return UploadResult(
        positions=positions,
        warnings=warnings,
        base_currency=_detect_base_currency(positions),
    )


def _dict_list_to_positions(raw: list[dict]) -> list[Position]:
    """Convierte la lista de dicts retornada por Gemini a objetos Position."""
    positions: list[Position] = []
    seen: set[str] = set()

    for item in raw:
        ticker = str(item.get("ticker") or "").upper().strip()
        if not ticker or ticker in seen:
            continue

        # Ignorar filas que claramente no son posiciones
        if _SKIP_ROW_PATTERNS.match(ticker):
            continue

        try:
            qty = float(item.get("quantity") or 0)
        except (ValueError, TypeError):
            continue

        if qty <= 0:
            continue

        def _safe_float(val) -> float | None:
            try:
                return float(val) if val is not None else None
            except (ValueError, TypeError):
                return None

        currency_raw = str(item.get("currency") or "USD").upper().strip()
        currency_map = {
            "ARS": "ARS", "PESOS": "ARS",
            "USD": "USD", "USDC": "USD", "USDM": "USD",
            "U$S": "USD", "U$S C": "USD",
        }
        currency = currency_map.get(currency_raw, "USD")

        positions.append(Position(
            ticker=ticker,
            name=str(item.get("name") or "")[:100] or None,
            quantity=qty,
            currency=currency,
            market_price=_safe_float(item.get("market_price")),
            market_value=_safe_float(item.get("market_value")),
            asset_type=item.get("asset_type"),
        ))
        seen.add(ticker)

    return positions


def _extract_pdf_text(file_bytes: bytes) -> str:
    """Extrae todo el texto de un PDF como string plano."""
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


def _parse_pdf_by_text(full_text: str) -> list[Position]:
    """
    Parsea el texto completo del PDF buscando líneas de posiciones.

    Formato Centaurus (cada línea de posición tiene la estructura):
    TICKER  DESCRIPCION  CANTIDAD  MONEDA  COTIZACION  IMPORTE  ...

    Ejemplo real:
    "YPFD YPF S.A. "D" ESCRITURALES 360 ARS $ 8.095,0000 $ 2.914.200,00 $ 1,00 ..."
    "YMCJO ON YPF S.A. REGS 1,5% V.30/09/2033 1.255 USDC U$S C 0,9751 ..."
    "BPOB7 BOPREAL S. 1 B VTO31/10/27 U$S CG 1.360 USD U$S 1,0414 ..."
    """
    positions: list[Position] = []
    lines = full_text.split("\n")

    # Detectar sección actual para asignar asset_type
    current_asset_type: str | None = None
    current_currency: str = "USD"

    # Tickers ya detectados para evitar duplicados
    seen_tickers: set[str] = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detectar cambio de sección
        line_lower = line.lower()
        for key, atype in _SECTION_ASSET_TYPES.items():
            if key in line_lower:
                current_asset_type = atype
                break

        # Detectar cambio de moneda de sección
        if re.search(r'pesos?\s+arg', line_lower):
            current_currency = "ARS"
        elif re.search(r'dólar|dolar|dollar', line_lower):
            current_currency = "USD"

        # Intentar extraer posición de la línea
        pos = _extract_position_from_line(line, current_asset_type, current_currency)
        if pos and pos.ticker not in seen_tickers:
            positions.append(pos)
            seen_tickers.add(pos.ticker)

    return positions


# Regex para detectar una línea de posición:
# - Empieza con un ticker (2-8 letras/números mayúsculas)
# - Seguido de descripción
# - Contiene un número que puede ser la cantidad
_POSITION_LINE_RE = re.compile(
    r'^([A-Z0-9]{2,8})\s+'           # ticker
    r'(.+?)\s+'                        # descripción (non-greedy)
    r'([\d\.]+(?:[\.,]\d+)?)\s+'      # cantidad
    r'(ARS|USD|USDC|USDM|U\$S\s*C?G?)\s+',  # moneda
    re.IGNORECASE
)

# Números con formato argentino o internacional
_NUMBER_RE = re.compile(r'\$?\s*([\d\.]+(?:,\d+)?)')


def _extract_position_from_line(
    line: str,
    asset_type: str | None,
    default_currency: str,
) -> Position | None:
    """
    Intenta extraer una posición de una línea de texto del PDF.
    Maneja el formato específico de Centaurus.
    """
    # Ignorar líneas que son claramente headers, totales o metadatos
    skip_patterns = [
        r'^(total|subtotal|hoja|tenencia|valuación|símbolo|simbolo|fecha|'
        r'denominación|denominacion|liquidez|acciones|obligaciones|títulos|titulos|'
        r'saldos|dólar|dolar|pesos|ars|usd|alyc|cuenta|jueves|lunes|martes|'
        r'miércoles|miercoles|viernes|sábado|sabado|domingo)',
        r'^\d{1,2}/\d{1,2}/\d{4}',  # fechas
        r'^[\$\d\s\.,\%]+$',          # solo números
    ]
    line_lower = line.lower().strip()
    for pattern in skip_patterns:
        if re.match(pattern, line_lower):
            return None

    # Intentar match con el regex de posición
    m = _POSITION_LINE_RE.match(line)
    if not m:
        return None

    ticker = m.group(1).upper().strip()
    name = m.group(2).strip()
    qty_str = m.group(3)
    currency_raw = m.group(4).strip().upper()

    # Ignorar tickers que son palabras comunes
    common_words = {"ARS", "USD", "TOTAL", "HOJA", "FECHA", "TIPO"}
    if ticker in common_words:
        return None

    quantity = _clean_number(qty_str)
    if not quantity or quantity <= 0:
        return None

    # Normalizar moneda
    currency_map = {
        "ARS": "ARS",
        "USD": "USD",
        "USDC": "USD",
        "USDM": "USD",
        "U$S": "USD",
        "U$S C": "USD",
        "U$S CG": "USD",
    }
    currency = currency_map.get(currency_raw, default_currency)

    # Intentar extraer cotización — buscar el primer número después de la moneda
    rest = line[m.end():]
    numbers = _NUMBER_RE.findall(rest)
    market_price = _clean_number(numbers[0]) if numbers else None

    # Intentar extraer market_value — buscar número más grande en la línea
    all_numbers = [_clean_number(n) for n in _NUMBER_RE.findall(line)]
    all_numbers = [n for n in all_numbers if n and n > quantity]
    market_value = max(all_numbers) if all_numbers else None

    return Position(
        ticker=ticker,
        name=name[:100] if name else None,
        quantity=quantity,
        currency=currency,
        market_price=market_price,
        market_value=market_value,
        asset_type=asset_type,
    )


def _parse_pdf_by_tables(file_bytes: bytes) -> list[Position]:
    """
    Fallback: intenta extraer posiciones de tablas con columnas separadas.
    Funciona con PDFs de brokers internacionales donde pdfplumber
    extrae columnas correctamente.
    """
    positions: list[Position] = []
    seen_tickers: set[str] = set()

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue
                # Buscar fila de headers con más de 1 columna
                for i, row in enumerate(table):
                    if len(row) > 1 and _is_header_row(row):
                        col_map = _map_columns([str(c or "").strip() for c in row])
                        if "ticker" not in col_map.values():
                            continue
                        for data_row in table[i + 1:]:
                            if len(data_row) < 2:
                                continue
                            pos = _row_to_position(data_row, col_map)
                            if pos and pos.ticker not in seen_tickers:
                                positions.append(pos)
                                seen_tickers.add(pos.ticker)
                        break

    return positions


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

async def parse_file(file_bytes: bytes, filename: str) -> UploadResult:
    """Detecta el formato por extensión y delega al parser correspondiente."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        return await parse_pdf(file_bytes)
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
