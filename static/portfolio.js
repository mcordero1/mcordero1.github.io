/**
 * portfolio.js — Portfolio Health Module
 *
 * Vanilla JS, sin dependencias externas.
 * Se conecta al backend FastAPI desplegado en Render.
 * Soporta SSE streaming para el análisis y el chat.
 */

(function () {
  "use strict";
  // ---------------------------------------------------------------------------
  // Configuración
  // ---------------------------------------------------------------------------

  // URL base del backend. En producción apunta al servicio de Render.
  // Para desarrollo local cambiar a "http://localhost:8000"
  const API_BASE =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1"
      ? "http://localhost:8000"
      : "https://mcordero1-github-io.onrender.com"; // URL del backend en Render

  const ENDPOINTS = {
    upload: `${API_BASE}/api/v1/portfolio/upload`,
    analyze: `${API_BASE}/api/v1/portfolio/analyze`,
    chat: `${API_BASE}/api/v1/portfolio/chat`,
  };

  // ---------------------------------------------------------------------------
  // Estado de la sesión (se descarta al cerrar la pestaña)
  // ---------------------------------------------------------------------------

  const state = {
    language: "es",
    positions: [],        // posiciones confirmadas
    reportSummary: null,  // resumen del reporte para el chat
    chatHistory: [],      // historial de mensajes del chat
  };

  // ---------------------------------------------------------------------------
  // Referencias DOM
  // ---------------------------------------------------------------------------

  const $ = (id) => document.getElementById(id);

  const els = {
    dropArea: $("ph-drop-area"),
    fileInput: $("ph-file-input"),
    dropTitle: $("ph-drop-title"),
    dropSub: $("ph-drop-sub"),
    uploadZone: $("ph-upload-zone"),
    positionsZone: $("ph-positions-zone"),
    positionsTitle: $("ph-positions-title"),
    positionsBody: $("ph-positions-body"),
    warnings: $("ph-warnings"),
    btnAnalyze: $("ph-btn-analyze"),
    btnRestart: $("ph-btn-restart"),
    reportZone: $("ph-report-zone"),
    chatZone: $("ph-chat-zone"),
    loading: $("ph-loading"),
    loadingMsg: $("ph-loading-msg"),
    // Score
    gaugeFill: $("ph-gauge-fill"),
    gaugeVal: $("ph-gauge-val"),
    dimDiv: $("ph-dim-div"), dimDivVal: $("ph-dim-div-val"),
    dimCor: $("ph-dim-cor"), dimCorVal: $("ph-dim-cor-val"),
    dimFx: $("ph-dim-fx"),   dimFxVal: $("ph-dim-fx-val"),
    dimLiq: $("ph-dim-liq"), dimLiqVal: $("ph-dim-liq-val"),
    dimVol: $("ph-dim-vol"), dimVolVal: $("ph-dim-vol-val"),
    // Métricas
    mVol: $("ph-m-vol"),
    mRet: $("ph-m-ret"),
    mSharpe: $("ph-m-sharpe"),
    mCorr: $("ph-m-corr"),
    mPair: $("ph-m-pair"),
    // Concentración y riesgos
    concBars: $("ph-concentration-bars"),
    risksList: $("ph-risks-list"),
    // Narrativa
    narrativeText: $("ph-narrative-text"),
    narrativeCursor: $("ph-narrative-cursor"),
    // Chat
    chatMessages: $("ph-chat-messages"),
    chatForm: $("ph-chat-form"),
    chatInput: $("ph-chat-input"),
    chatSend: document.querySelector(".ph-chat-send"),
  };

  // ---------------------------------------------------------------------------
  // Idioma
  // ---------------------------------------------------------------------------

  const i18n = {
    es: {
      dropTitle: "Arrastrá tu archivo aquí",
      dropSub: "o hacé clic para seleccionar · PDF, Excel (.xlsx) o CSV · máx. 10 MB",
      positionsTitle: "Posiciones detectadas",
      analyzeBtn: "Analizar cartera →",
      loadingUpload: "Procesando archivo…",
      loadingAnalyze: "Analizando cartera…",
      chatPlaceholder: "Escribí tu pregunta…",
      chatHint: "Por ejemplo: '¿Qué pasa si agrego NVDA?' · '¿Cuál es mi activo más volátil?'",
      dimLabels: ["Diversificación", "Correlación", "Exposición FX", "Liquidez", "Volatilidad"],
      metricLabels: ["Volatilidad anual", "Retorno esperado", "Sharpe Ratio", "Correlación prom.", "Par correlacionado"],
      concentration: "Concentración sectorial",
      risks: "Riesgos detectados",
      analysis: "Análisis",
      restart: "Analizar otra cartera",
      na: "N/D",
    },
    en: {
      dropTitle: "Drag your file here",
      dropSub: "or click to select · PDF, Excel (.xlsx) or CSV · max 10 MB",
      positionsTitle: "Detected positions",
      analyzeBtn: "Analyze portfolio →",
      loadingUpload: "Processing file…",
      loadingAnalyze: "Analyzing portfolio…",
      chatPlaceholder: "Type your question…",
      chatHint: 'e.g. "What if I add NVDA?" · "What is my most volatile asset?"',
      dimLabels: ["Diversification", "Correlation", "FX Exposure", "Liquidity", "Volatility"],
      metricLabels: ["Annual volatility", "Expected return", "Sharpe Ratio", "Avg correlation", "Most correlated pair"],
      concentration: "Sector concentration",
      risks: "Detected risks",
      analysis: "Analysis",
      restart: "Analyze another portfolio",
      na: "N/A",
    },
  };

  function t(key) {
    return (i18n[state.language] || i18n.es)[key] || key;
  }

  // ---------------------------------------------------------------------------
  // Helpers UI
  // ---------------------------------------------------------------------------

  function show(el) { el.classList.remove("ph-hidden"); }
  function hide(el) { el.classList.add("ph-hidden"); }

  function showLoading(msg) {
    els.loadingMsg.textContent = msg;
    show(els.loading);
  }

  function hideLoading() {
    hide(els.loading);
  }

  function scoreColor(val) {
    if (val >= 70) return "#9ae9c3";    // verde
    if (val >= 40) return "#f0c040";    // amarillo
    return "#e05050";                   // rojo
  }

  function barClass(val) {
    if (val >= 70) return "ph-bar-green";
    if (val >= 40) return "ph-bar-yellow";
    return "ph-bar-red";
  }

  function fmtPct(val, decimals = 1) {
    if (val === null || val === undefined) return t("na");
    return (val * 100).toFixed(decimals) + "%";
  }

  function fmtNum(val, decimals = 2) {
    if (val === null || val === undefined) return t("na");
    return Number(val).toFixed(decimals);
  }

  // Renderizado básico de markdown en texto plano
  function renderMarkdown(text) {
    return text
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`(.+?)`/g, "<code>$1</code>")
      .replace(/^### (.+)$/gm, "<strong>$1</strong>")
      .replace(/^## (.+)$/gm, "<strong>$1</strong>")
      .replace(/^- (.+)$/gm, "• $1")
      .replace(/\n{2,}/g, "\n\n");
  }

  // ---------------------------------------------------------------------------
  // Toggle de idioma
  // ---------------------------------------------------------------------------

  document.querySelectorAll(".ph-lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.language = btn.dataset.lang;
      document.querySelectorAll(".ph-lang-btn").forEach((b) => {
        b.classList.toggle("ph-lang-active", b.dataset.lang === state.language);
        b.setAttribute("aria-pressed", b.dataset.lang === state.language ? "true" : "false");
      });
      updateLanguageUI();
    });
  });

  function updateLanguageUI() {
    els.dropTitle.textContent = t("dropTitle");
    els.dropSub.textContent = t("dropSub");
    if (els.positionsTitle) els.positionsTitle.textContent = t("positionsTitle");
    if (els.btnAnalyze) els.btnAnalyze.innerHTML = t("analyzeBtn");
    if (els.chatInput) els.chatInput.placeholder = t("chatPlaceholder");
    if (els.btnRestart) els.btnRestart.textContent = t("restart");
  }

  // ---------------------------------------------------------------------------
  // Drag & Drop y file input
  // ---------------------------------------------------------------------------

  els.dropArea.addEventListener("click", () => els.fileInput.click());

  els.dropArea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      els.fileInput.click();
    }
  });

  els.dropArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    els.dropArea.classList.add("ph-drop-hover");
  });

  els.dropArea.addEventListener("dragleave", () => {
    els.dropArea.classList.remove("ph-drop-hover");
  });

  els.dropArea.addEventListener("drop", (e) => {
    e.preventDefault();
    els.dropArea.classList.remove("ph-drop-hover");
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  });

  els.fileInput.addEventListener("change", () => {
    const file = els.fileInput.files[0];
    if (file) handleFile(file);
  });

  // ---------------------------------------------------------------------------
  // Validación y upload del archivo
  // ---------------------------------------------------------------------------

  const ALLOWED_EXTS = ["pdf", "xlsx", "xls", "csv"];
  const MAX_SIZE = 10 * 1024 * 1024;

  function handleFile(file) {
    const ext = file.name.split(".").pop().toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
      showFileError(`Formato no soportado: .${ext}. Usá PDF, Excel (.xlsx) o CSV.`);
      return;
    }
    if (file.size > MAX_SIZE) {
      showFileError("El archivo supera el límite de 10 MB.");
      return;
    }
    uploadFile(file);
  }

  function showFileError(msg) {
    els.dropTitle.textContent = "⚠ " + msg;
    els.dropTitle.style.color = "#e05050";
    setTimeout(() => {
      els.dropTitle.textContent = t("dropTitle");
      els.dropTitle.style.color = "";
    }, 4000);
  }

  async function uploadFile(file) {
    showLoading(t("loadingUpload"));

    const formData = new FormData();
    formData.append("file", file);
    formData.append("language", state.language);

    try {
      const res = await fetch(ENDPOINTS.upload, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Error al subir el archivo.");
      }

      const data = await res.json();
      hideLoading();
      renderPositions(data.positions, data.warnings || []);
    } catch (err) {
      hideLoading();
      showFileError(err.message || "Error de conexión con el servidor.");
    }
  }

  // ---------------------------------------------------------------------------
  // Tabla de posiciones
  // ---------------------------------------------------------------------------

  function renderPositions(positions, warnings) {
    state.positions = positions;

    // Warnings
    els.warnings.innerHTML = "";
    warnings.forEach((w) => {
      const div = document.createElement("div");
      div.className = "ph-warning-item";
      div.setAttribute("role", "alert");
      div.textContent = "⚠ " + w.message;
      els.warnings.appendChild(div);
    });

    // Tabla
    els.positionsBody.innerHTML = "";
    positions.forEach((pos, idx) => {
      const tr = document.createElement("tr");
      tr.dataset.idx = idx;

      const fields = [
        { key: "ticker", val: pos.ticker },
        { key: "name", val: pos.name || "—" },
        { key: "quantity", val: pos.quantity != null ? pos.quantity : "—" },
        { key: "market_price", val: pos.market_price != null ? pos.market_price : "—" },
        { key: "avg_cost", val: pos.avg_cost != null ? pos.avg_cost : "—" },
        { key: "currency", val: pos.currency || "USD" },
        { key: "asset_type", val: pos.asset_type || "—" },
        { key: "sector", val: pos.sector || "—" },
      ];

      fields.forEach(({ key, val }) => {
        const td = document.createElement("td");
        const input = document.createElement("input");
        input.type = "text";
        input.value = val;
        input.setAttribute("aria-label", key);
        input.addEventListener("change", (e) => {
          updatePosition(idx, key, e.target.value);
        });
        td.appendChild(input);
        tr.appendChild(td);
      });

      els.positionsBody.appendChild(tr);
    });

    hide(els.uploadZone);
    show(els.positionsZone);
  }

  function updatePosition(idx, field, value) {
    if (!state.positions[idx]) return;
    const numFields = ["quantity", "market_price", "avg_cost", "market_value", "weight"];
    if (numFields.includes(field)) {
      const num = parseFloat(value.replace(",", "."));
      state.positions[idx][field] = isNaN(num) ? null : num;
    } else {
      state.positions[idx][field] = value === "—" ? null : value;
    }
  }

  // ---------------------------------------------------------------------------
  // Análisis con SSE streaming
  // ---------------------------------------------------------------------------

  els.btnAnalyze.addEventListener("click", startAnalysis);

  async function startAnalysis() {
    if (!state.positions.length) return;

    showLoading(t("loadingAnalyze"));
    hide(els.positionsZone);
    hide(els.reportZone);
    hide(els.chatZone);

    const body = JSON.stringify({
      positions: state.positions,
      language: state.language,
      base_currency: "USD",
    });

    try {
      const res = await fetch(ENDPOINTS.analyze, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Error al analizar la cartera.");
      }

      hideLoading();
      show(els.reportZone);

      // Resetear narrativa
      els.narrativeText.innerHTML = "";
      show(els.narrativeCursor);

      await readSSEStream(res, handleAnalysisEvent);

      hide(els.narrativeCursor);
      show(els.chatZone);
    } catch (err) {
      hideLoading();
      show(els.positionsZone);
      showFileError(err.message || "Error de conexión con el servidor.");
    }
  }

  function handleAnalysisEvent(eventName, data) {
    switch (eventName) {
      case "score":
        renderScore(data);
        break;
      case "report":
        renderReport(data);
        // Guardar resumen para el chat
        state.reportSummary = {
          score: data.score,
          metrics: data.metrics,
          concentration: data.concentration,
          risks: data.risks,
          positions: state.positions,
        };
        break;
      case "narrative":
        // Streaming token por token
        els.narrativeText.innerHTML += renderMarkdown(data);
        els.narrativeText.scrollIntoView({ behavior: "smooth", block: "nearest" });
        break;
      case "done":
        hide(els.narrativeCursor);
        break;
      case "error":
        els.narrativeText.textContent =
          "Error al generar el análisis: " + (data.message || "error desconocido");
        break;
    }
  }

  // ---------------------------------------------------------------------------
  // Render del score y el reporte
  // ---------------------------------------------------------------------------

  function renderScore(score) {
    const val = score.total;

    // Gauge SVG: el arco tiene 251px de longitud total (semicírculo de r=80)
    const ARC = 251;
    const offset = ARC - (val / 100) * ARC;
    els.gaugeFill.style.strokeDashoffset = offset;
    els.gaugeFill.style.stroke = scoreColor(val);
    els.gaugeVal.textContent = Math.round(val);

    // Barras de dimensiones
    const dims = [
      { bar: els.dimDiv, val: els.dimDivVal, score: score.diversification },
      { bar: els.dimCor, val: els.dimCorVal, score: score.correlation },
      { bar: els.dimFx, val: els.dimFxVal,   score: score.fx_exposure },
      { bar: els.dimLiq, val: els.dimLiqVal, score: score.liquidity },
      { bar: els.dimVol, val: els.dimVolVal, score: score.volatility },
    ];

    dims.forEach(({ bar, val: valEl, score: s }) => {
      bar.style.width = s + "%";
      bar.className = "ph-dim-bar " + barClass(s);
      bar.setAttribute("aria-valuenow", s);
      valEl.textContent = Math.round(s);
    });
  }

  function renderReport(report) {
    const m = report.metrics || {};
    const na = t("na");

    // Métricas cuantitativas
    els.mVol.textContent = m.volatility_annual != null ? fmtPct(m.volatility_annual) : na;
    els.mRet.textContent = m.expected_return_annual != null ? fmtPct(m.expected_return_annual) : na;
    els.mSharpe.textContent = m.sharpe_ratio != null ? fmtNum(m.sharpe_ratio) : na;
    els.mCorr.textContent = m.avg_pairwise_correlation != null ? fmtNum(m.avg_pairwise_correlation) : na;
    els.mPair.textContent =
      m.most_correlated_pair && m.most_correlated_pair.length >= 2
        ? m.most_correlated_pair.join(" / ") + " (" + fmtNum(m.most_correlated_value) + ")"
        : na;

    // Concentración sectorial
    els.concBars.innerHTML = "";
    (report.concentration || []).slice(0, 10).forEach((item) => {
      const pct = Math.round(item.weight * 100);
      const div = document.createElement("div");
      div.className = "ph-conc-item";
      div.setAttribute("role", "listitem");
      div.innerHTML = `
        <span class="ph-conc-name">${escHtml(item.sector)}</span>
        <div class="ph-conc-bar-wrap" role="presentation">
          <div class="ph-conc-bar" style="width:${pct}%" role="progressbar"
               aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"
               aria-label="${escHtml(item.sector)} ${pct}%"></div>
        </div>
        <span class="ph-conc-pct">${pct}%</span>`;
      els.concBars.appendChild(div);
    });

    // Riesgos detectados
    els.risksList.innerHTML = "";
    (report.risks || []).forEach((risk) => {
      const icon = risk.level === "red" ? "🔴" : risk.level === "yellow" ? "🟡" : "🟢";
      const cls = `ph-risk-item ph-risk-${risk.level}`;
      const li = document.createElement("li");
      li.className = cls;
      li.innerHTML = `
        <span class="ph-risk-icon" aria-hidden="true">${icon}</span>
        <div class="ph-risk-content">
          <p class="ph-risk-label">${escHtml(risk.label)}</p>
          <p class="ph-risk-detail">${escHtml(risk.detail)}</p>
        </div>`;
      els.risksList.appendChild(li);
    });
  }

  // ---------------------------------------------------------------------------
  // Chat de seguimiento
  // ---------------------------------------------------------------------------

  els.chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const msg = els.chatInput.value.trim();
    if (!msg) return;
    sendChatMessage(msg);
    els.chatInput.value = "";
  });

  function appendMessage(role, text) {
    const div = document.createElement("div");
    div.className = `ph-msg ph-msg-${role}`;
    const avatar = role === "user" ? "U" : "PH";
    div.innerHTML = `
      <div class="ph-msg-avatar" aria-hidden="true">${avatar}</div>
      <div class="ph-msg-bubble" lang="${state.language}">${
        role === "agent" ? renderMarkdown(escHtml(text)) : escHtml(text)
      }</div>`;
    els.chatMessages.appendChild(div);
    els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
    return div.querySelector(".ph-msg-bubble");
  }

  function appendTypingIndicator() {
    const div = document.createElement("div");
    div.className = "ph-msg ph-msg-agent";
    div.id = "ph-typing-indicator";
    div.innerHTML = `
      <div class="ph-msg-avatar" aria-hidden="true">PH</div>
      <div class="ph-msg-bubble">
        <div class="ph-typing" aria-label="Escribiendo…">
          <span></span><span></span><span></span>
        </div>
      </div>`;
    els.chatMessages.appendChild(div);
    els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
    return div;
  }

  async function sendChatMessage(message) {
    if (els.chatSend) els.chatSend.disabled = true;

    // Agregar mensaje del usuario
    appendMessage("user", message);
    state.chatHistory.push({ role: "user", content: message });

    // Indicador de escritura
    const typingEl = appendTypingIndicator();

    const body = JSON.stringify({
      message,
      history: state.chatHistory.slice(-10), // máx últimos 10 mensajes
      report_summary: state.reportSummary,
      language: state.language,
    });

    try {
      const res = await fetch(ENDPOINTS.chat, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Error en el chat.");
      }

      // Reemplazar indicador de escritura con burbuja de respuesta
      typingEl.remove();
      const bubble = appendMessage("agent", "");
      let fullResponse = "";

      await readSSEStream(res, (eventName, data) => {
        if (eventName === "chunk") {
          fullResponse += data;
          bubble.innerHTML = renderMarkdown(escHtml(fullResponse));
          els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
        }
      });

      state.chatHistory.push({ role: "assistant", content: fullResponse });
    } catch (err) {
      typingEl.remove();
      appendMessage("agent", "Error: " + (err.message || "Error de conexión."));
    } finally {
      if (els.chatSend) els.chatSend.disabled = false;
      els.chatInput.focus();
    }
  }

  // ---------------------------------------------------------------------------
  // SSE reader genérico
  // ---------------------------------------------------------------------------

  async function readSSEStream(response, onEvent) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Procesar líneas completas
      const lines = buffer.split("\n");
      buffer = lines.pop(); // última línea puede estar incompleta

      let currentEvent = "message";
      for (const line of lines) {
        if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          const rawData = line.slice(6);
          try {
            const parsed = JSON.parse(rawData);
            onEvent(currentEvent, parsed);
          } catch {
            // data no es JSON (ej. chunk de texto)
            onEvent(currentEvent, rawData);
          }
          currentEvent = "message"; // resetear para el siguiente evento
        }
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Restart
  // ---------------------------------------------------------------------------

  els.btnRestart.addEventListener("click", () => {
    // Resetear estado
    state.positions = [];
    state.reportSummary = null;
    state.chatHistory = [];

    // Resetear UI
    els.fileInput.value = "";
    els.positionsBody.innerHTML = "";
    els.warnings.innerHTML = "";
    els.narrativeText.innerHTML = "";
    els.chatMessages.innerHTML = "";
    els.gaugeFill.style.strokeDashoffset = 251;
    els.gaugeVal.textContent = "—";

    hide(els.reportZone);
    hide(els.chatZone);
    hide(els.positionsZone);
    show(els.uploadZone);
  });

  // ---------------------------------------------------------------------------
  // Utilidades
  // ---------------------------------------------------------------------------

  function escHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // Inicializar textos según idioma por defecto
  updateLanguageUI();
})();
