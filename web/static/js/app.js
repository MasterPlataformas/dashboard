// ============================================================================
// CONFIGURAÇÃO E VARIÁVEIS GLOBAIS
// ============================================================================
const COLORS = {
    auto: '#00ffd1', imovel: '#ff9100', pesado: '#0b8cf7',
    gold: '#FFB300', green: '#4CAF50', white: '#FFFFFF',
    bg3: '#141C30', bg4: '#1A2440', navy: '#0D1B3E',
    border: '#1E2D50', plotBg: '#10192C', plotGrid: '#22304F',
    text: '#E0E8FF', text2: '#8899BB', text3: '#556080'
};

let appData = { vagas: { auto: [], imovel: [], pesado: [] }, historico: {}, config: {} };
let rotIndex = { auto: 0, imovel: 0, pesado: 0 };
let chartInstances = {};
const renderTimeouts = new Map();
const rotationIntervalMs = {};
const rotationIntervals = {};

// ============================================================================
// PLUGIN: LABELS NOS PONTOS
// ============================================================================
const valueLabelsPlugin = {
    id: 'valueLabels',
    afterDatasetsDraw(chart) {
        const { ctx } = chart;
        ctx.save();
        chart.data.datasets.forEach((dataset, datasetIndex) => {
            const meta = chart.getDatasetMeta(datasetIndex);
            if (meta.hidden) return;
            meta.data.forEach((element, index) => {
                const rawValue = dataset.data[index];
                if (rawValue === null || rawValue === undefined || Number.isNaN(rawValue)) return;
                const pos = element.tooltipPosition();
                if (!pos) return;
                const isBar = (dataset.type || meta.type || chart.config.type) === 'bar';
                const value = Number(rawValue);
                const formatted = isBar ? String(Math.round(value)) : value.toFixed(1);
                let offsetY = isBar ? -10 : (dataset.label === 'Min' ? 13 : -14);
                ctx.font = "bold 11px 'Segoe UI'";
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                const labelColor = isBar
                    ? (dataset.valueLabelColor || COLORS.green)
                    : (dataset.label === 'Min' ? COLORS.white : (dataset.borderColor || COLORS.text));
                ctx.fillStyle = labelColor;
                ctx.fillText(formatted, pos.x, pos.y + offsetY);
            });
        });
        ctx.restore();
    }
};

// ============================================================================
// PLUGIN: PREENCHIMENTO MANUAL ENTRE MIN E MAX (GRADIENTE)
// ============================================================================
const fillBetweenPlugin = {
    id: 'fillBetween',
    beforeDatasetsDraw(chart) {
        const datasets = chart.data.datasets;
        if (datasets.length < 2) return;
        const maxMeta = chart.getDatasetMeta(0);
        const minMeta = chart.getDatasetMeta(1);
        if (!maxMeta || !minMeta || !maxMeta.data.length) return;
        const { ctx, chartArea } = chart;
        ctx.save();
        ctx.beginPath();
        maxMeta.data.forEach((point, i) => {
            if (i === 0) ctx.moveTo(point.x, point.y);
            else ctx.lineTo(point.x, point.y);
        });
        for (let i = minMeta.data.length - 1; i >= 0; i--) {
            ctx.lineTo(minMeta.data[i].x, minMeta.data[i].y);
        }
        ctx.closePath();
        const color = chart.config._fillColor || '#60A7EA';
        const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
        gradient.addColorStop(0, color + '55');
        gradient.addColorStop(1, color + '11');
        ctx.fillStyle = gradient;
        ctx.fill();
        ctx.restore();
    }
};

// ============================================================================
// UTILITÁRIOS
// ============================================================================
function destroyChart(id) {
    if (chartInstances[id]) { chartInstances[id].destroy(); delete chartInstances[id]; }
}

function updateTime() {
    const now = new Date();
    document.getElementById('clock').innerText = now.toLocaleTimeString('pt-BR');
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    let dateStr = now.toLocaleDateString('pt-BR', options);
    document.getElementById('date').innerText = dateStr.charAt(0).toUpperCase() + dateStr.slice(1);
}
setInterval(updateTime, 1000);
updateTime();


function formatMonth(dateStr, short = false) {
    const ptShort = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
    const ptLong  = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
    const d = new Date(dateStr);
    d.setMinutes(d.getMinutes() + d.getTimezoneOffset());
    const month = short ? ptShort[d.getMonth()] : ptLong[d.getMonth()];
    return month;
}

// Para eixo X: usa versão curta quando muitos meses, longa quando poucos
function formatMonthAxis(dateStr, totalPoints) {
    return formatMonth(dateStr, totalPoints > 6);
}

function getVisibleTickIndexes(totalPoints, maxTicks = 7) {
    if (totalPoints <= 0) return new Set();
    if (totalPoints <= maxTicks) return new Set(Array.from({ length: totalPoints }, (_, i) => i));

    const indexes = new Set([0, totalPoints - 1]);
    const step = (totalPoints - 1) / (maxTicks - 1);
    for (let i = 1; i < maxTicks - 1; i++) {
        indexes.add(Math.round(i * step));
    }
    return indexes;
}

function normalizeGroupId(value) {
    return String(value || '').trim().toUpperCase();
}

function getFavoriteGroups(cat) {
    const colConfig = appData.config[cat] || {};
    let favs = colConfig.favoritos || [];
    if (typeof favs === 'string') favs = favs.split('\n').map(s => s.trim()).filter(Boolean);
    return favs.map(normalizeGroupId).filter(Boolean);
}

function getRegularSlotCount(cat) {
    const colConfig = appData.config[cat] || {};
    const configured = Math.max(0, Number(colConfig.vagas_simultaneas || 2));
    return Math.max(0, configured - (getFavoriteGroups(cat).length > 0 ? 1 : 0));
}

function getGroupDisplaySeconds(cat) {
    const colConfig = appData.config[cat] || {};
    return Math.max(3, Number(colConfig.tempo_grupo_segundos || 12));
}

function drawEmptyChart(canvasId, label) {
    destroyChart(canvasId);
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.font = "italic 13px 'Segoe UI'";
    ctx.fillStyle = COLORS.text3;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, canvas.width / 2, canvas.height / 2);
    ctx.restore();
}

function getHistoryMetrics(histData) {
    if (!histData || histData.length === 0) return null;
    const sorted = [...histData].sort((a, b) => new Date(a.Mes) - new Date(b.Mes));
    const last = sorted[sorted.length - 1];
    const tail3 = sorted.slice(-3);
    const media = (Number(last.Lance_Min) + Number(last.Lance_Max)) / 2;
    const media3m = tail3.reduce((s, r) => s + (Number(r.Lance_Min) + Number(r.Lance_Max)) / 2, 0) / tail3.length;
    return {
        media, media3m,
        min: Number(last.Lance_Min), max: Number(last.Lance_Max),
        cont: Number(last.QT_Contemp),
        periodo: formatMonth(last.Mes, false)
    };
}


// ============================================================================
// ROTAÇÃO DE GRUPOS
// ============================================================================
function restartRotationLoop(cat) {
    const intervalMs = getGroupDisplaySeconds(cat) * 1000;
    if (rotationIntervals[cat]) clearInterval(rotationIntervals[cat]);
    rotationIntervals[cat] = setInterval(() => {
        rotIndex[cat] += getRegularSlotCount(cat) || 1;
        renderColumn(cat, true); // true = animate transition
    }, intervalMs);
    rotationIntervalMs[cat] = intervalMs;
}

function syncRotationLoop(cat) {
    const intervalMs = getGroupDisplaySeconds(cat) * 1000;
    if (!rotationIntervals[cat] || rotationIntervalMs[cat] !== intervalMs) {
        restartRotationLoop(cat);
    }
}

function syncAllRotationLoops() {
    ['auto', 'imovel', 'pesado'].forEach(syncRotationLoop);
}

function restartAllRotationLoops() {
    ['auto', 'imovel', 'pesado'].forEach(restartRotationLoop);
}

let _rotationStarted = false;

async function fetchData() {
    try {
        const response = await fetch('/api/data');
        if (!response.ok) throw new Error('Network error');
        const data = await response.json();
        appData = data;
        const numGrupos = Object.keys(data.historico).length;
        document.getElementById('status-bar').innerHTML =
            `✔ Atualizado ${new Date().toLocaleTimeString('pt-BR')} | Histórico: ${numGrupos} grupos`;
        renderAllColumns();
        if (!_rotationStarted) {
            restartAllRotationLoops();
            _rotationStarted = true;
        } else {
            syncAllRotationLoops();
        }
    } catch (error) {
        document.getElementById('status-bar').innerHTML = `❌ Erro de conexão: ${error.message}`;
    }
}

function renderSummaryTable(histData, color) {
    if (!histData || histData.length === 0) {
        return `<table class="summary-table">
            <tr><th>Período</th><th>Média %</th><th>Contemp.</th></tr>
            <tr><td>12m</td><td>—</td><td>—</td></tr>
            <tr><td>6m</td><td>—</td><td>—</td></tr>
            <tr><td>3m</td><td>—</td><td>—</td></tr>
        </table>`;
    }
    const sorted = [...histData].sort((a, b) => new Date(a.Mes) - new Date(b.Mes));
    const getStats = (n) => {
        const tail = sorted.slice(-n);
        if (!tail.length) return { med: '—', cont: '—' };
        const sumMin = tail.reduce((s, r) => s + Number(r.Lance_Min), 0);
        const sumMax = tail.reduce((s, r) => s + Number(r.Lance_Max), 0);
        return {
            med: ((sumMin + sumMax) / (2 * tail.length)).toFixed(2) + '%',
            cont: tail.reduce((s, r) => s + Number(r.QT_Contemp), 0)
        };
    };
    const s12 = getStats(12), s6 = getStats(6), s3 = getStats(3);
    return `
        <table class="summary-table">
            <tr><th style="color:${color}">Período</th><th style="color:${color}">Média %</th><th style="color:${color}">Contemp.</th></tr>
            <tr><td style="color:${COLORS.text2}">12m</td><td style="color:${s12.med!=='—'?color:COLORS.text3}">${s12.med}</td><td style="color:${COLORS.green}">${s12.cont}</td></tr>
            <tr><td style="color:${COLORS.text2}">6m</td><td style="color:${s6.med!=='—'?color:COLORS.text3}">${s6.med}</td><td style="color:${COLORS.green}">${s6.cont}</td></tr>
            <tr><td style="color:${COLORS.text2}">3m</td><td style="color:${s3.med!=='—'?color:COLORS.text3}">${s3.med}</td><td style="color:${COLORS.green}">${s3.cont}</td></tr>
        </table>`;
}

function renderHighlights(histData, color) {
    const m = getHistoryMetrics(histData);
    if (!m) return `<div class="card-highlights"><div class="highlight-box"><div class="hl-title">Histórico</div><div class="hl-val" style="color:${COLORS.text3}">Sem dados</div></div></div>`;
    const delta = m.media - m.media3m;
    let deltaTxt = 'Estável vs 3m', deltaColor = COLORS.text2;
    if (Math.abs(delta) >= 0.05) {
        deltaTxt = `${delta > 0 ? '▲' : '▼'} ${Math.abs(delta).toFixed(2)}% vs 3m`;
        deltaColor = delta > 0 ? '#FF6B6B' : COLORS.green;
    }
    return `
        <div class="card-highlights">
            <div class="highlight-box">
                <div class="hl-title">Lance médio</div>
                <div class="hl-val" style="color:${color}">${m.media.toFixed(2)}%</div>
                <div class="hl-desc" style="color:${deltaColor}">${deltaTxt}</div>
            </div>
            <div class="highlight-box" style="background:linear-gradient(135deg,var(--navy),var(--bg4))">
                <div class="hl-title">Faixa do mês</div>
                <div class="hl-val" style="color:var(--white);font-size:13px">${m.min.toFixed(1)}% — ${m.max.toFixed(1)}%</div>
                <div class="hl-desc">Min · Max · ${m.periodo}</div>
            </div>
            <div class="highlight-box">
                <div class="hl-title">Contemplações</div>
                <div class="hl-val" style="color:${COLORS.green}">${m.cont}</div>
                <div class="hl-desc">Média 3m: ${m.media3m.toFixed(2)}%</div>
            </div>
        </div>`;
}

// ============================================================================
// GRÁFICOS
// ============================================================================
function renderChartPair(lineCanvasId, barCanvasId, histData, color) {
    const lineCanvas = document.getElementById(lineCanvasId);
    const barCanvas = document.getElementById(barCanvasId);
    const timeoutKey = `${lineCanvasId}|${barCanvasId}`;
    if (renderTimeouts.has(timeoutKey)) { clearTimeout(renderTimeouts.get(timeoutKey)); renderTimeouts.delete(timeoutKey); }
    destroyChart(lineCanvasId);
    destroyChart(barCanvasId);

    if (!histData || histData.length === 0) {
        drawEmptyChart(lineCanvasId, 'Sem histórico');
        drawEmptyChart(barCanvasId, 'Sem histórico');
        return;
    }

    const draw = () => {
        if (!lineCanvas || !barCanvas) return;
        if (lineCanvas.offsetWidth === 0 || barCanvas.offsetWidth === 0) {
            renderTimeouts.set(timeoutKey, setTimeout(draw, 50)); return;
        }

        const sorted = [...histData].sort((a, b) => new Date(a.Mes) - new Date(b.Mes)).slice(-7);
        const n = sorted.length;
        const labels  = sorted.map(r => formatMonthAxis(r.Mes, n));
        const dataMin = sorted.map(r => Number(r.Lance_Min) || 0);
        const dataMax = sorted.map(r => Number(r.Lance_Max) || 0);
        const dataCont = sorted.map(r => Number(r.QT_Contemp) || 0);
        const minY = Math.min(...dataMin), maxY = Math.max(...dataMax);
        const maxCont = Math.max(...dataCont, 0);

        const tooltip = {
            backgroundColor: 'rgba(10,14,26,0.97)',
            titleColor: COLORS.white, bodyColor: COLORS.text,
            borderColor: color, borderWidth: 1, padding: 10,
            callbacks: {
                title: (items) => {
                    // Tooltip title: mostra mês completo
                    const idx = items[0].dataIndex;
                    return formatMonth(sorted[idx].Mes, false);
                },
                label: (ctx) => {
                    const v = ctx.parsed.y;
                    if (ctx.dataset.label === 'Contemplações') return ` ${Math.round(v)} contemplações`;
                    return ` ${ctx.dataset.label}: ${v.toFixed(2)}%`;
                }
            }
        };

        const fillPlugin = {
            ...fillBetweenPlugin,
            beforeDatasetsDraw(chart) { chart.config._fillColor = color; fillBetweenPlugin.beforeDatasetsDraw.call(this, chart); }
        };

        chartInstances[lineCanvasId] = new Chart(lineCanvas.getContext('2d'), {
            type: 'line',
            plugins: [fillPlugin, valueLabelsPlugin],
            data: {
                labels,
                datasets: [
                    {
                        label: 'Max', data: dataMax,
                        borderColor: color, backgroundColor: 'transparent',
                        borderWidth: 2.5,
                        pointBackgroundColor: COLORS.bg4, pointBorderColor: color,
                        pointBorderWidth: 2, pointRadius: 4, pointHoverRadius: 7,
                        fill: false, tension: 0.3
                    },
                    {
                        label: 'Min', data: dataMin,
                        borderColor: COLORS.white, backgroundColor: 'transparent',
                        borderWidth: 2,
                        pointBackgroundColor: COLORS.bg4, pointBorderColor: COLORS.white,
                        pointBorderWidth: 2, pointRadius: 4, pointHoverRadius: 7,
                        fill: false, tension: 0.3
                    }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                animation: { duration: 650, easing: 'easeOutCubic' },
                layout: { padding: { top: 25, right: 8, bottom: 10, left: 0 } },
                plugins: { legend: { display: false }, tooltip },
                scales: {
                    x: {
                        offset: false,
                        grid: { display: false },
                        ticks: {
                            color: COLORS.text2,
                            autoSkip: false, maxTicksLimit: 7,
                            maxRotation: 0, minRotation: 0,
                            padding: 8,
                            font: { size: 11 }
                        }
                    },
                    y: {
                        beginAtZero: false,
                        suggestedMin: minY - 1.6, suggestedMax: maxY + 1.9,
                        title: { display: true, text: '%', color: COLORS.text2, font: { size: 11 } },
                        grid: { color: COLORS.plotGrid, borderDash: [3, 3] },
                        ticks: { color: COLORS.text2, font: { size: 11 } }
                    }
                }
            }
        });

        // GRÁFICO DE BARRAS - CORRIGIDO (offset: true e padding)
        chartInstances[barCanvasId] = new Chart(barCanvas.getContext('2d'), {
            type: 'bar',
            plugins: [valueLabelsPlugin],
            data: {
                labels,
                datasets: [{
                    label: 'Contemplações', data: dataCont,
                    backgroundColor: dataCont.map((_, i) => i === n - 1 ? color + 'FF' : color + '77'),
                    borderColor: dataCont.map((_, i) => i === n - 1 ? color : 'transparent'),
                    valueLabelColor: COLORS.white,
                    borderWidth: 1, borderRadius: 4,
                    barPercentage: 0.7,
                    categoryPercentage: 0.8
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                animation: { duration: 700, easing: 'easeOutCubic' },
                layout: {
                    padding: {
                        top: 20,
                        right: 20,
                        bottom: 10,
                        left: 20
                    }
                },
                plugins: { legend: { display: false }, tooltip },
                scales: {
                    x: {
                        offset: true,   // ALTERADO PARA true - evita corte das barras
                        grid: { display: false },
                        ticks: {
                            color: COLORS.text2,
                            autoSkip: false, maxTicksLimit: 7,
                            maxRotation: 0, minRotation: 0,
                            padding: 8,
                            font: { size: 11 }
                        }
                    },
                    y: {
                        beginAtZero: true, suggestedMax: maxCont > 0 ? maxCont * 1.28 : 1,
                        ticks: { color: COLORS.text2, stepSize: 1, precision: 0, font: { size: 11 } },
                        grid: { color: COLORS.plotGrid, borderDash: [3, 3] }
                    }
                }
            }
        });

        const container = lineCanvas.closest('.chart-grid');
        if (container && !container.__resizeObserver) {
            const observer = new ResizeObserver(() => setTimeout(() => {
                if (chartInstances[lineCanvasId]) chartInstances[lineCanvasId].resize();
                if (chartInstances[barCanvasId]) chartInstances[barCanvasId].resize();
            }, 50));
            observer.observe(container);
            container.__resizeObserver = observer;
        }
    };

    requestAnimationFrame(draw);
}

// ============================================================================
// CARDS E COLUNAS
// ============================================================================
function buildCardHTML(cat, grupo, vagaRow, histData, isFav, idx) {
    const cardClass = isFav ? 'card-fav' : `card-${cat}`;
    const mainColor = isFav ? COLORS.gold : COLORS[cat];
    const lineCanvasId = `chart-line-${cat}-${idx}`;
    const barCanvasId = `chart-bar-${cat}-${idx}`;
    const metrics = getHistoryMetrics(histData);
    const baseLabel = metrics ? `Base: ${metrics.periodo}` : 'Sem dados históricos';

    let disponivelHTML = '';
    if (vagaRow) {
        const cMin = vagaRow['Crédito mínimo'] || vagaRow['Credito minimo'] || '—';
        const cMax = vagaRow['Crédito máximo'] || vagaRow['Credito maximo'] || '—';
        const valParcela = vagaRow['Valor médio parcela'] || '—';
        const meses = vagaRow['Meses restantes'] || '—';
        const vagasLivres = vagaRow._vagas_livres ?? '—';
        disponivelHTML = `
            <div class="card-info">
                <div class="info-item"><span class="info-label">Crédito</span><span class="info-val">${cMin} → ${cMax}</span></div>
                <div class="info-item"><span class="info-label">Parcela</span><span class="info-val">${valParcela}</span></div>
                <div class="info-item"><span class="info-label">Prazo</span><span class="info-val">${meses}</span></div>
                <div class="info-item"><span class="info-label">Vagas livres</span><span class="info-val">${vagasLivres}</span></div>
            </div>`;
    } else {
        disponivelHTML = `<div class="card-info"><span style="color:var(--orange);font-size:11px;font-style:italic;">Grupo indisponível no momento</span></div>`;
    }

    return `
        <div class="card ${cardClass}">
            <div class="card-header">
                <div class="card-group"><span class="card-group-label">GRUPO</span><span class="card-group-val">${grupo}</span></div>
                ${disponivelHTML}
                <div class="card-table">${renderSummaryTable(histData, mainColor)}</div>
            </div>
            ${renderHighlights(histData, mainColor)}
            <div class="card-chart">
                <div class="chart-head">
                    <div class="chart-head-title">Histórico de lances</div>
                    <div class="chart-head-base">${baseLabel}</div>
                </div>
                <div class="chart-grid">
                    <div class="chart-panel chart-panel-line">
                        <div class="chart-title">Lances Min/Max (%)</div>
                        <canvas id="${lineCanvasId}"></canvas>
                    </div>
                    <div class="chart-panel chart-panel-bar">
                        <div class="chart-title">Contemplações</div>
                        <canvas id="${barCanvasId}"></canvas>
                    </div>
                </div>
            </div>
        </div>`;
}

function renderColumn(cat) {
    const colConfig = appData.config[cat] || {};
    const vagasData = appData.vagas[cat] || [];
    let favs = colConfig.favoritos || [];
    if (typeof favs === 'string') favs = favs.split('\n').map(s => s.trim()).filter(Boolean);
    const vagasSimul = colConfig.vagas_simultaneas || 2;
    const gruposRot = vagasData.map(v => v.Grupo).filter(g => !favs.includes(g));

    const container = document.getElementById(`cards-${cat}`);
    container.innerHTML = '';
    const chartsToRender = [];
    let currentIdx = 0;

    if (favs.length > 0) {
        const grupo = favs[0];
        const row = vagasData.find(v => v.Grupo === grupo);
        const hist = appData.historico[grupo] || [];
        container.innerHTML += buildCardHTML(cat, grupo, row, hist, true, currentIdx);
        chartsToRender.push({ lineId: `chart-line-${cat}-${currentIdx}`, barId: `chart-bar-${cat}-${currentIdx}`, hist, color: COLORS.gold });
        currentIdx++;
    }

    if (gruposRot.length > 0) {
        for (let i = 0; i < vagasSimul; i++) {
            const idx = (rotIndex[cat] + i) % gruposRot.length;
            const grupo = gruposRot[idx];
            const row = vagasData.find(v => v.Grupo === grupo);
            const hist = appData.historico[grupo] || [];
            container.innerHTML += buildCardHTML(cat, grupo, row, hist, false, currentIdx);
            chartsToRender.push({ lineId: `chart-line-${cat}-${currentIdx}`, barId: `chart-bar-${cat}-${currentIdx}`, hist, color: COLORS[cat] });
            currentIdx++;
        }
        const total = gruposRot.length;
        const start = (rotIndex[cat] % total) + 1;
        const end = Math.min(start + vagasSimul - 1, total);
        const shown = Array.from({ length: vagasSimul }, (_, i) => gruposRot[(rotIndex[cat] + i) % total]);
        document.getElementById(`prog-${cat}`).innerText = `${start}-${end} / ${total} (${shown.join(' · ')})`;
    } else {
        for (let i = 0; i < vagasSimul; i++) {
            container.innerHTML += buildCardHTML(cat, '---', null, [], false, currentIdx);
            chartsToRender.push({ lineId: `chart-line-${cat}-${currentIdx}`, barId: `chart-bar-${cat}-${currentIdx}`, hist: [], color: COLORS[cat] });
            currentIdx++;
        }
        document.getElementById(`prog-${cat}`).innerText = '';
    }

    setTimeout(() => chartsToRender.forEach(c => renderChartPair(c.lineId, c.barId, c.hist, c.color)), 30);
}

function renderAllColumns() {
    renderColumn('auto'); renderColumn('imovel'); renderColumn('pesado');
}

// ============================================================================
// PAINEL DE CONTROLE (EXTRAÇÃO)
// ============================================================================
function toggleControlPanel() {
    const modal = document.getElementById('control-panel');
    modal.style.display = modal.style.display === 'block' ? 'none' : 'block';
    if (modal.style.display === 'block') pollStatus();
}

async function startExtraction() {
    const user = document.getElementById('ext-user').value;
    const pass = document.getElementById('ext-pass').value;
    const btn = document.getElementById('btn-start-ext');
    try {
        btn.disabled = true; btn.innerText = '⌛ Iniciando...';
        const res = await fetch('/api/extrair', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ usuario: user, senha: pass }) });
        const result = await res.json();
        if (res.ok) { pollStatus(); }
        else { alert('Erro: ' + (result.error || 'Falha')); btn.disabled = false; btn.innerText = '🚀 Iniciar Nova Extração'; }
    } catch (e) { alert('Erro: ' + e.message); btn.disabled = false; btn.innerText = '🚀 Iniciar Nova Extração'; }
}

let statusInterval = null;
async function pollStatus() {
    if (statusInterval) return;
    statusInterval = setInterval(async () => {
        try {
            const status = await (await fetch('/api/status')).json();
            const dot = document.getElementById('ext-status-dot');
            const text = document.getElementById('ext-status-text');
            const log = document.getElementById('ext-log');
            const progress = document.getElementById('ext-progress-bar');
            const btn = document.getElementById('btn-start-ext');
            if (status.rodando) { dot.classList.add('active'); text.innerText = 'Extraindo...'; btn.disabled = true; btn.innerText = '⌛ Em andamento...'; }
            else { dot.classList.remove('active'); text.innerText = 'Aguardando...'; btn.disabled = false; btn.innerText = '🚀 Iniciar Nova Extração'; if (status.progresso === 100) fetchData(); }
            log.innerText = status.ultimo_log || '---';
            progress.style.width = status.progresso + '%';
            progress.innerText = status.progresso + '%';
            const modal = document.getElementById('control-panel');
            if (modal.style.display !== 'block' && !status.rodando) { clearInterval(statusInterval); statusInterval = null; }
        } catch (e) { console.error(e); }
    }, 2000);
}

// ============================================================================
// PAINEL DE CONFIGURAÇÕES
// ============================================================================
let configData = {};
let gruposData = {};

async function openConfigPanel() {
    document.getElementById('config-panel').style.display = 'block';
    await loadConfigPanel();
}

function closeConfigPanel() {
    document.getElementById('config-panel').style.display = 'none';
}

async function loadConfigPanel() {
    try {
        const [cfgRes, grpRes] = await Promise.all([fetch('/api/config'), fetch('/api/grupos')]);
        configData = await cfgRes.json();
        gruposData = await grpRes.json();
        renderConfigPanel();
    } catch (e) {
        alert('Erro ao carregar configurações: ' + e.message);
    }
}

function renderConfigPanel() {
    // Caminhos dos arquivos
    document.getElementById('cfg-base-dir').innerText = configData.base_dir || '—';
    document.getElementById('cfg-hist-input').value = configData.historico_path || '';
    document.getElementById('cfg-hist-exists').innerText = configData.historico_existe ? '✅ Encontrado' : '❌ Não encontrado';
    document.getElementById('cfg-hist-exists').style.color = configData.historico_existe ? '#4CAF50' : '#FF6B6B';

    ['auto', 'imovel', 'pesado'].forEach(cat => {
        const catCfg = configData[cat] || {};
        document.getElementById(`cfg-${cat}-input`).value = catCfg.arquivo_atual || '';
        const existsEl = document.getElementById(`cfg-${cat}-exists`);
        existsEl.innerText = catCfg.arquivo_existe ? '✅ Encontrado' : '❌ Não encontrado';
        existsEl.style.color = catCfg.arquivo_existe ? '#4CAF50' : '#FF6B6B';

        // Filtros de meses
        document.getElementById(`cfg-${cat}-min-meses`).value = catCfg.min_meses || 0;
        document.getElementById(`cfg-${cat}-max-meses`).value = catCfg.max_meses === 999 || !catCfg.max_meses ? '' : catCfg.max_meses;
        document.getElementById(`cfg-${cat}-max-vagas`).value = catCfg.max_vagas_livres || '';
        document.getElementById(`cfg-${cat}-tempo-grupo`).value = catCfg.tempo_grupo_segundos || 12;

        // Grupos disponíveis
        renderGruposList(cat, gruposData[cat] || [], catCfg.favoritos || []);
    });
}

function renderGruposList(cat, grupos, favoritoAtual) {
    const container = document.getElementById(`cfg-${cat}-grupos`);
    if (!grupos.length) {
        container.innerHTML = '<div style="color:#556080;font-style:italic;font-size:12px">Nenhum grupo carregado</div>';
        return;
    }

    // Agrupa por faixa
    const porFaixa = {};
    grupos.forEach(g => {
        const f = g.faixa || 'Sem faixa';
        if (!porFaixa[f]) porFaixa[f] = [];
        porFaixa[f].push(g);
    });

    let html = '';
    Object.entries(porFaixa).forEach(([faixa, items]) => {
        html += `<div class="cfg-faixa-label">📁 ${faixa}</div>`;
        items.forEach(g => {
            const isFav = favoritoAtual === g.grupo || (Array.isArray(favoritoAtual) && favoritoAtual.includes(g.grupo));
            const mesesNum = Math.round(Number(g.meses) || 0);
            const mesesColor = mesesNum <= 36 ? '#4CAF50' : mesesNum <= 72 ? '#FFB300' : '#FF6B6B';
            html += `
                <div class="cfg-grupo-item" id="grp-${cat}-${g.grupo}">
                    <div class="cfg-grupo-info">
                        <span class="cfg-grupo-nome">${g.grupo}</span>
                        <span class="cfg-grupo-meses" style="color:${mesesColor}">${mesesNum} meses</span>
                    </div>
                    <button class="cfg-fav-btn ${isFav ? 'active' : ''}" onclick="toggleFavorito('${cat}','${g.grupo}')">
                        ${isFav ? '⭐ Favorito' : '☆ Favoritar'}
                    </button>
                </div>`;
        });
    });
    container.innerHTML = html;
}

function toggleFavorito(cat, grupo) {
    const catCfg = configData[cat] || {};
    let favs = catCfg.favoritos || [];
    if (typeof favs === 'string') favs = [favs];
    const idx = favs.indexOf(grupo);
    if (idx >= 0) favs.splice(idx, 1);
    else favs = [grupo, ...favs];
    configData[cat] = { ...catCfg, favoritos: favs };
    renderGruposList(cat, gruposData[cat] || [], favs);
}

function filterGrupos(cat, searchTerm) {
    const items = document.querySelectorAll(`#cfg-${cat}-grupos .cfg-grupo-item`);
    items.forEach(item => {
        const nome = item.querySelector('.cfg-grupo-nome').innerText.toLowerCase();
        item.style.display = nome.includes(searchTerm.toLowerCase()) ? '' : 'none';
    });
}

async function saveConfig() {
    try {
        const payload = {};

        // Caminhos dos arquivos
        const histPath = document.getElementById('cfg-hist-input').value.trim();
        if (histPath) payload.historico = histPath;

        ['auto', 'imovel', 'pesado'].forEach(cat => {
            const minMeses = parseInt(document.getElementById(`cfg-${cat}-min-meses`).value) || 0;
            const maxMesesVal = document.getElementById(`cfg-${cat}-max-meses`).value;
            const maxMeses = maxMesesVal ? parseInt(maxMesesVal) : 999;
            const maxVagasVal = document.getElementById(`cfg-${cat}-max-vagas`).value;
            const maxVagas = maxVagasVal ? parseInt(maxVagasVal) : 200;
            const tempoGrupoVal = document.getElementById(`cfg-${cat}-tempo-grupo`).value;
            const tempoGrupo = tempoGrupoVal ? parseInt(tempoGrupoVal) : 12;
            const arquivoPath = document.getElementById(`cfg-${cat}-input`).value.trim();
            payload[cat] = {
                min_meses: minMeses,
                max_meses: maxMeses,
                max_vagas_livres: maxVagas,
                tempo_grupo_segundos: Math.max(3, tempoGrupo),
                favoritos: (configData[cat] || {}).favoritos || [],
                ...(arquivoPath ? { arquivo: arquivoPath } : {})
            };
        });

        const res = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const result = await res.json();
        if (result.success) {
            showToast('✅ Configurações salvas!');
            closeConfigPanel();
            await fetchData();
        } else {
            alert('Erro ao salvar: ' + result.error);
        }
    } catch (e) {
        alert('Erro: ' + e.message);
    }
}

function showToast(msg) {
    let toast = document.getElementById('toast-msg');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast-msg';
        document.body.appendChild(toast);
    }
    toast.innerText = msg;
    toast.style.cssText = 'position:fixed;bottom:30px;right:30px;background:#1A3A6B;color:#fff;padding:12px 20px;border-radius:8px;border:1px solid #4FC3F7;z-index:9999;font-size:14px;box-shadow:0 4px 20px rgba(0,0,0,0.5)';
    setTimeout(() => { if (toast) toast.style.display = 'none'; }, 3000);
}

// ============================================================================
// ESTILOS DINÂMICOS
// ============================================================================
const style = document.createElement('style');
style.textContent = `
    .chart-grid { display:flex; gap:10px; margin-top:8px; }
    .chart-panel { flex:1; min-width:0; background:var(--plotBg,#10192C); border-radius:8px; padding:10px; border:1px solid var(--border); }
    .chart-panel-line { flex:1.2; }
    .chart-panel-bar { flex:0.8; }
    .chart-panel canvas { display:block; width:100% !important; height:180px !important; min-height:180px; }
    .chart-title { font-size:11px; color:${COLORS.text3}; margin-bottom:4px; text-align:center; text-transform:uppercase; letter-spacing:0.5px; }
    .chart-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:5px; padding:0 2px; }
    .chart-head-title { font-size:11px; font-weight:bold; color:${COLORS.text2}; text-transform:uppercase; letter-spacing:0.5px; }
    .chart-head-base { font-size:10px; color:${COLORS.text3}; font-style:italic; }

    /* Config Panel */
    #config-panel { display:none; position:fixed; z-index:2000; left:0; top:0; width:100%; height:100%; background:rgba(0,0,0,0.85); backdrop-filter:blur(5px); overflow-y:auto; }
    .config-panel-content { background:var(--bg2,#0F1525); margin:20px auto; max-width:900px; border-radius:12px; border:1px solid var(--border); overflow:hidden; }
    .config-panel-header { background:var(--navy); padding:15px 20px; display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid var(--orange); }
    .config-panel-header h2 { font-size:18px; margin:0; color:var(--white); }
    .config-close { color:var(--text2); font-size:28px; cursor:pointer; background:none; border:none; }
    .config-close:hover { color:var(--white); }
    .config-tabs { display:flex; background:var(--bg3); border-bottom:1px solid var(--border); }
    .config-tab { flex:1; padding:10px; text-align:center; cursor:pointer; font-size:13px; color:var(--text2); border:none; background:none; transition:all 0.2s; }
    .config-tab.active { color:var(--cyan); border-bottom:2px solid var(--cyan); background:var(--bg4); }
    .config-tab-content { display:none; padding:20px; }
    .config-tab-content.active { display:block; }
    .cfg-section { margin-bottom:20px; }
    .cfg-section h4 { color:var(--cyan); font-size:13px; text-transform:uppercase; letter-spacing:1px; margin-bottom:12px; padding-bottom:6px; border-bottom:1px solid var(--border); }
    .cfg-path-edit { display:flex; align-items:center; gap:10px; }
    .cfg-path-input { flex:1; background:var(--bg); border:1px solid var(--border); padding:9px 12px; color:var(--text); border-radius:6px; font-size:12px; font-family:monospace; transition:border-color 0.2s; }
    .cfg-path-input:focus { outline:none; border-color:var(--cyan); box-shadow:0 0 0 2px rgba(79,195,247,0.15); }
    .cfg-path-input::placeholder { color:#556080; }
    .cfg-status { font-size:12px; white-space:nowrap; font-weight:bold; }
    .cfg-filters { display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:10px; margin-top:10px; }
    .cfg-filter-item label { display:block; font-size:11px; color:var(--text2); margin-bottom:4px; }
    .cfg-filter-item input { width:100%; background:var(--bg); border:1px solid var(--border); padding:8px; color:var(--text); border-radius:4px; font-size:13px; }
    .cfg-filter-item input:focus { outline:none; border-color:var(--cyan); }
    .cfg-search { width:100%; background:var(--bg); border:1px solid var(--border); padding:8px 12px; color:var(--text); border-radius:6px; font-size:13px; margin-bottom:10px; }
    .cfg-search:focus { outline:none; border-color:var(--cyan); }
    .cfg-grupos-list { max-height:280px; overflow-y:auto; border:1px solid var(--border); border-radius:6px; padding:8px; background:var(--bg); }
    .cfg-faixa-label { font-size:11px; color:var(--text3); text-transform:uppercase; letter-spacing:1px; padding:6px 4px 4px; border-top:1px solid var(--border); margin-top:4px; }
    .cfg-faixa-label:first-child { border-top:none; margin-top:0; }
    .cfg-grupo-item { display:flex; justify-content:space-between; align-items:center; padding:6px 8px; border-radius:4px; margin:2px 0; transition:background 0.15s; }
    .cfg-grupo-item:hover { background:var(--bg3); }
    .cfg-grupo-info { display:flex; flex-direction:column; gap:2px; }
    .cfg-grupo-nome { font-size:13px; font-weight:bold; color:var(--text); }
    .cfg-grupo-meses { font-size:11px; }
    .cfg-fav-btn { background:var(--bg3); border:1px solid var(--border); color:var(--text2); padding:4px 10px; border-radius:4px; cursor:pointer; font-size:12px; transition:all 0.2s; }
    .cfg-fav-btn:hover { background:var(--bg4); }
    .cfg-fav-btn.active { background:rgba(255,179,0,0.15); border-color:var(--gold); color:var(--gold); }
    .cfg-save-btn { width:100%; background:var(--orange); color:var(--white); border:none; padding:12px; font-weight:bold; cursor:pointer; border-radius:6px; font-size:14px; margin-top:20px; transition:background 0.2s; }
    .cfg-save-btn:hover { background:#e65100; }
    .cat-header-auto { color:var(--auto-acc,#60A7EA); }
    .cat-header-imovel { color:var(--imovel-acc,#FF1212); }
    .cat-header-pesado { color:var(--pesado-acc,#D849FC); }
`;
document.head.appendChild(style);

// Injeta o painel de configurações no DOM
document.addEventListener('DOMContentLoaded', () => {
    const panel = document.createElement('div');
    panel.id = 'config-panel';
    panel.innerHTML = `
        <div class="config-panel-content">
            <div class="config-panel-header">
                <h2>⚙️ Configurações do Dashboard</h2>
                <button class="config-close" onclick="closeConfigPanel()">×</button>
            </div>
            <div class="config-tabs">
                <button class="config-tab active" onclick="switchConfigTab('arquivos')">📁 Arquivos</button>
                <button class="config-tab" onclick="switchConfigTab('auto')"> Automóveis</button>
                <button class="config-tab" onclick="switchConfigTab('imovel')"> Imóveis</button>
                <button class="config-tab" onclick="switchConfigTab('pesado')"> Pesados</button>
            </div>

            <!-- ABA ARQUIVOS -->
            <div class="config-tab-content active" id="cfg-tab-arquivos">
                <div class="cfg-section">
                    <h4>📂 Diretório Base do Servidor</h4>
                    <div class="cfg-path-box"><span class="cfg-path-text" id="cfg-base-dir">—</span></div>
                    <div style="font-size:11px;color:#556080;margin-top:6px">ℹ️ Caminho onde o <code>app.py</code> está sendo executado. Os caminhos abaixo podem ser absolutos ou relativos a este diretório.</div>
                </div>
                <div class="cfg-section">
                    <h4>📊 Arquivo de Histórico (Lances)</h4>
                    <div class="cfg-path-edit">
                        <input type="text" class="cfg-path-input" id="cfg-hist-input" placeholder="Ex: C:\\extrator\\Lances Master Prime.xlsx">
                        <span class="cfg-status" id="cfg-hist-exists">—</span>
                    </div>
                </div>
                ${['auto','imovel','pesado'].map(cat => `
                <div class="cfg-section">
                    <h4 class="cat-header-${cat}">${cat === 'auto' ? ' Automóveis' : cat === 'imovel' ? ' Imóveis' : ' Pesados'} — Arquivo de Vagas</h4>
                    <div class="cfg-path-edit">
                        <input type="text" class="cfg-path-input" id="cfg-${cat}-input" placeholder="Ex: C:\\extrator\\vagas_${cat === 'auto' ? 'automoveis' : cat === 'imovel' ? 'imoveis' : 'veiculos_pesados'}.xlsx">
                        <span class="cfg-status" id="cfg-${cat}-exists">—</span>
                    </div>
                </div>`).join('')}
                <div style="background:rgba(79,195,247,0.07);border:1px solid #1E2D50;border-radius:8px;padding:12px 16px;margin-top:8px;font-size:12px;color:#8899BB;line-height:1.7">
                    💡 <strong style="color:#4FC3F7">Dica:</strong> Cole o caminho completo onde o extrator salva os arquivos.<br>
                    Após salvar, o status mostrará <span style="color:#4CAF50">✅ Encontrado</span> ou <span style="color:#FF6B6B">❌ Não encontrado</span>.<br>
                    Use barras duplas <code>\\\\</code> no Windows ou barras normais <code>/</code>.
                </div>
            </div>

            <!-- ABAS POR CATEGORIA -->
            ${['auto','imovel','pesado'].map(cat => `
            <div class="config-tab-content" id="cfg-tab-${cat}">
                <div class="cfg-section">
                    <h4>🔧 Filtros de Prazo</h4>
                    <div class="cfg-filters">
                        <div class="cfg-filter-item">
                            <label>Mínimo de meses</label>
                            <input type="number" id="cfg-${cat}-min-meses" placeholder="0 (sem limite)">
                        </div>
                        <div class="cfg-filter-item">
                            <label>Máximo de meses</label>
                            <input type="number" id="cfg-${cat}-max-meses" placeholder="Sem limite">
                        </div>
                        <div class="cfg-filter-item">
                            <label>Máx. vagas livres</label>
                            <input type="number" id="cfg-${cat}-max-vagas" placeholder="200">
                        </div>
                        <div class="cfg-filter-item">
                            <label>Tempo por grupo (s)</label>
                            <input type="number" id="cfg-${cat}-tempo-grupo" placeholder="12">
                        </div>
                    </div>
                </div>
                <div class="cfg-section">
                    <h4>⭐ Grupos — Favorito e Filtro</h4>
                    <input class="cfg-search" type="text" placeholder="🔍 Buscar grupo..." oninput="filterGrupos('${cat}', this.value)">
                    <div class="cfg-grupos-list" id="cfg-${cat}-grupos">
                        <div style="color:#556080;font-style:italic;font-size:12px">Carregando...</div>
                    </div>
                </div>
            </div>`).join('')}

            <div style="padding:0 20px 20px">
                <button class="cfg-save-btn" onclick="saveConfig()">💾 Salvar Configurações</button>
            </div>
        </div>`;
    document.body.appendChild(panel);

    // Adiciona botão de configurações no header
    const headerControls = document.querySelector('.controls-trigger');
    if (headerControls) {
        const cfgBtn = document.createElement('div');
        cfgBtn.className = 'controls-trigger';
        cfgBtn.style.cssText = 'background:rgba(79,195,247,0.1);border-color:#4FC3F7;color:#4FC3F7;margin-right:8px';
        cfgBtn.innerHTML = '⚙️ Configurações';
        cfgBtn.onclick = openConfigPanel;
        headerControls.parentNode.insertBefore(cfgBtn, headerControls);
    }
});

function switchConfigTab(name) {
    document.querySelectorAll('.config-tab').forEach((t, i) => {
        const tabs = ['arquivos','auto','imovel','pesado'];
        t.classList.toggle('active', tabs[i] === name);
    });
    document.querySelectorAll('.config-tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(`cfg-tab-${name}`).classList.add('active');
}

// ============================================================================
// INICIALIZAÇÃO
// ============================================================================
function getHistoryGroupsSet() {
    return new Set((gruposData.historico_todos || []).map(normalizeGroupId));
}

function addManualFavorito(cat) {
    const input = document.getElementById(`cfg-${cat}-manual-fav`);
    if (!input) return;
    const grupo = normalizeGroupId(input.value);
    if (!grupo) return showToast('Informe um grupo para favoritar.');
    if (!getHistoryGroupsSet().has(grupo)) return showToast('Esse grupo não foi encontrado no histórico.');

    const catCfg = configData[cat] || {};
    let favs = catCfg.favoritos || [];
    if (typeof favs === 'string') favs = [favs];
    favs = [grupo, ...favs.map(normalizeGroupId).filter(f => f && f !== grupo)];
    configData[cat] = { ...catCfg, favoritos: favs };
    input.value = '';
    renderGruposList(cat, gruposData[cat] || [], favs);
    showToast(`Grupo ${grupo} adicionado aos favoritos.`);
}

function ensureManualFavoriteUI(cat) {
    const targetTab = document.getElementById(`cfg-tab-${cat}`);
    if (!targetTab || document.getElementById(`cfg-${cat}-manual-wrap`)) return;
    const searchEl = targetTab.querySelector('.cfg-search');
    if (!searchEl) return;

    const wrap = document.createElement('div');
    wrap.id = `cfg-${cat}-manual-wrap`;
    wrap.className = 'cfg-manual-fav';
    wrap.innerHTML = `
        <div class="cfg-manual-title">Favorito manual via histórico</div>
        <div class="cfg-manual-row">
            <input class="cfg-path-input" id="cfg-${cat}-manual-fav" type="text" placeholder="Ex: 12345">
            <button class="cfg-fav-btn" type="button" onclick="addManualFavorito('${cat}')">Adicionar</button>
        </div>
        <div class="cfg-manual-desc">Use quando o grupo não saiu no extrator, mas existe no histórico.</div>`;
    searchEl.parentNode.insertBefore(wrap, searchEl);
}

function formatDurationFromSeconds(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    if (minutes <= 0) return `${seconds}s`;
    return `${minutes}min ${String(seconds).padStart(2, '0')}s`;
}

function upsertRotationSummary(cat) {
    const targetTab = document.getElementById(`cfg-tab-${cat}`);
    if (!targetTab) return;

    let box = document.getElementById(`cfg-${cat}-rotation-summary`);
    if (!box) {
        box = document.createElement('div');
        box.id = `cfg-${cat}-rotation-summary`;
        box.className = 'cfg-rotation-box';
        const section = targetTab.querySelector('.cfg-section');
        if (section) section.appendChild(box);
    }

    const total = (gruposData[cat] || []).length;
    const configured = Math.max(0, Number(document.getElementById(`cfg-${cat}-tempo-grupo`)?.value || configData[cat]?.tempo_grupo_segundos || 12));
    const pairSize = 2;
    const cycles = total > 0 ? Math.ceil(total / pairSize) : 0;
    const totalSeconds = cycles * configured;
    box.innerHTML = `
        <strong style="color:var(--white)">Tempo estimado para mostrar todos os grupos:</strong><br>
        ${total} grupos, ${pairSize} por vez, ${configured}s por tela.<br>
        Total estimado: <span style="color:var(--gold)">${formatDurationFromSeconds(totalSeconds)}</span>`;
}

renderConfigPanel = function() {
    document.getElementById('cfg-base-dir').innerText = configData.base_dir || '—';
    document.getElementById('cfg-hist-input').value = configData.historico_path || '';
    document.getElementById('cfg-hist-exists').innerText = configData.historico_existe ? '✅ Encontrado' : '❌ Não encontrado';
    document.getElementById('cfg-hist-exists').style.color = configData.historico_existe ? '#4CAF50' : '#FF6B6B';

    ['auto', 'imovel', 'pesado'].forEach(cat => {
        const catCfg = configData[cat] || {};
        document.getElementById(`cfg-${cat}-input`).value = catCfg.arquivo_atual || '';
        const existsEl = document.getElementById(`cfg-${cat}-exists`);
        existsEl.innerText = catCfg.arquivo_existe ? '✅ Encontrado' : '❌ Não encontrado';
        existsEl.style.color = catCfg.arquivo_existe ? '#4CAF50' : '#FF6B6B';
        document.getElementById(`cfg-${cat}-min-meses`).value = catCfg.min_meses || 0;
        document.getElementById(`cfg-${cat}-max-meses`).value = catCfg.max_meses === 999 || !catCfg.max_meses ? '' : catCfg.max_meses;
        document.getElementById(`cfg-${cat}-max-vagas`).value = catCfg.max_vagas_livres || '';
        document.getElementById(`cfg-${cat}-tempo-grupo`).value = catCfg.tempo_grupo_segundos || 12;
        ensureManualFavoriteUI(cat);
        upsertRotationSummary(cat);
        const tempoInput = document.getElementById(`cfg-${cat}-tempo-grupo`);
        if (tempoInput && !tempoInput.dataset.boundSummary) {
            tempoInput.addEventListener('input', () => upsertRotationSummary(cat));
            tempoInput.dataset.boundSummary = '1';
        }
        renderGruposList(cat, gruposData[cat] || [], catCfg.favoritos || []);
    });
};

renderGruposList = function(cat, grupos, favoritoAtual) {
    const container = document.getElementById(`cfg-${cat}-grupos`);
    const favs = (Array.isArray(favoritoAtual) ? favoritoAtual : [favoritoAtual]).map(normalizeGroupId).filter(Boolean);
    const availableGroups = (grupos || []).map(g => ({ ...g, grupo: normalizeGroupId(g.grupo), origem: g.origem || 'extrator' }));
    const availableSet = new Set(availableGroups.map(g => g.grupo));
    const manualHistoryFavorites = favs.filter(g => !availableSet.has(g)).map(g => ({ grupo: g, meses: 0, faixa: 'Somente histórico', origem: 'historico' }));
    const mergedGroups = [...manualHistoryFavorites, ...availableGroups];

    if (!mergedGroups.length) {
        container.innerHTML = '<div style="color:#556080;font-style:italic;font-size:12px">Nenhum grupo carregado</div>';
        return;
    }

    const porFaixa = {};
    mergedGroups.forEach(g => {
        const f = g.faixa || 'Sem faixa';
        if (!porFaixa[f]) porFaixa[f] = [];
        porFaixa[f].push(g);
    });

    let html = '';
    Object.entries(porFaixa).forEach(([faixa, items]) => {
        html += `<div class="cfg-faixa-label">📁 ${faixa}</div>`;
        items.forEach(g => {
            const isFav = favs.includes(g.grupo);
            const mesesNum = Math.round(Number(g.meses) || 0);
            const mesesText = g.origem === 'historico' ? 'Histórico apenas' : `${mesesNum} meses`;
            const mesesColor = g.origem === 'historico' ? '#4FC3F7' : (mesesNum <= 36 ? '#4CAF50' : mesesNum <= 72 ? '#FFB300' : '#FF6B6B');
            html += `
                <div class="cfg-grupo-item" id="grp-${cat}-${g.grupo}">
                    <div class="cfg-grupo-info">
                        <span class="cfg-grupo-nome">${g.grupo}</span>
                        <span class="cfg-grupo-meses" style="color:${mesesColor}">${mesesText}</span>
                    </div>
                    <button class="cfg-fav-btn ${isFav ? 'active' : ''}" onclick="toggleFavorito('${cat}','${g.grupo}')">
                        ${isFav ? '⭐ Favorito' : '☆ Favoritar'}
                    </button>
                </div>`;
        });
    });
    container.innerHTML = html;
};

toggleFavorito = function(cat, grupo) {
    const catCfg = configData[cat] || {};
    let favs = catCfg.favoritos || [];
    if (typeof favs === 'string') favs = [favs];
    favs = favs.map(normalizeGroupId).filter(Boolean);
    grupo = normalizeGroupId(grupo);
    const idx = favs.indexOf(grupo);
    if (idx >= 0) favs.splice(idx, 1);
    else favs = [grupo, ...favs];
    configData[cat] = { ...catCfg, favoritos: favs };
    renderGruposList(cat, gruposData[cat] || [], favs);
};

buildCardHTML = function(cat, grupo, vagaRow, histData, isFav, idx) {
    const cardClass = isFav ? 'card-fav' : `card-${cat}`;
    const mainColor = isFav ? COLORS.gold : COLORS[cat];
    const lineCanvasId = `chart-line-${cat}-${idx}`;
    const barCanvasId = `chart-bar-${cat}-${idx}`;
    const metrics = getHistoryMetrics(histData);
    const baseLabel = metrics ? `Base: ${metrics.periodo}` : 'Sem dados históricos';

    let disponivelHTML = '';
    if (vagaRow) {
        const cMin = vagaRow['Crédito mínimo'] || vagaRow['Credito minimo'] || vagaRow['CrÃ©dito mÃ­nimo'] || '—';
        const cMax = vagaRow['Crédito máximo'] || vagaRow['Credito maximo'] || vagaRow['CrÃ©dito mÃ¡ximo'] || '—';
        const valParcela = vagaRow['Valor médio parcela'] || vagaRow['Valor mÃ©dio parcela'] || '—';
        const meses = vagaRow['Meses restantes'] || '—';
        const vagasLivres = vagaRow._vagas_livres ?? '—';
        disponivelHTML = `
            <div class="card-info">
                <div class="info-item"><span class="info-label">Crédito</span><span class="info-val">${cMin} → ${cMax}</span></div>
                <div class="info-item"><span class="info-label">Parcela</span><span class="info-val">${valParcela}</span></div>
                <div class="info-item"><span class="info-label">Prazo</span><span class="info-val">${meses}</span></div>
                <div class="info-item"><span class="info-label">Vagas livres</span><span class="info-val">${vagasLivres}</span></div>
            </div>`;
    } else {
        const fallbackText = histData && histData.length > 0 ? 'Favorito exibido apenas com histórico' : 'Grupo indisponível no momento';
        disponivelHTML = `<div class="card-info"><span style="color:var(--orange);font-size:11px;font-style:italic;">${fallbackText}</span></div>`;
    }

    return `
        <div class="card ${cardClass}">
            <div class="card-header">
                <div class="card-group"><span class="card-group-label">GRUPO</span><span class="card-group-val">${grupo}</span></div>
                ${disponivelHTML}
                <div class="card-table">${renderSummaryTable(histData, mainColor)}</div>
            </div>
            ${renderHighlights(histData, mainColor)}
            <div class="card-chart">
                <div class="chart-head">
                    <div class="chart-head-title">Histórico de lances</div>
                    <div class="chart-head-base">${baseLabel}</div>
                </div>
                <div class="chart-grid">
                    <div class="chart-panel chart-panel-line">
                        <div class="chart-title">Lances Min/Max (%)</div>
                        <canvas id="${lineCanvasId}"></canvas>
                    </div>
                    <div class="chart-panel chart-panel-bar">
                        <div class="chart-title">Contemplações</div>
                        <canvas id="${barCanvasId}"></canvas>
                    </div>
                </div>
            </div>
        </div>`;
};

renderColumn = function(cat, animate = false) {
    const vagasData = appData.vagas[cat] || [];
    const favs = getFavoriteGroups(cat);
    const regularSlots = getRegularSlotCount(cat);
    const gruposRot = vagasData.map(v => normalizeGroupId(v.Grupo)).filter(g => !favs.includes(g));

    const container = document.getElementById(`cards-${cat}`);
    const chartsToRender = [];
    let currentIdx = 0;

    // Build new HTML
    let newHTML = '';

    if (favs.length > 0) {
        const grupo = normalizeGroupId(favs[0]);
        const row = vagasData.find(v => normalizeGroupId(v.Grupo) === grupo);
        const hist = appData.historico[grupo] || [];
        newHTML += buildCardHTML(cat, grupo, row, hist, true, currentIdx);
        chartsToRender.push({ lineId: `chart-line-${cat}-${currentIdx}`, barId: `chart-bar-${cat}-${currentIdx}`, hist, color: COLORS.gold });
        currentIdx++;
    }

    if (gruposRot.length > 0 && regularSlots > 0) {
        for (let i = 0; i < regularSlots; i++) {
            const idx = (rotIndex[cat] + i) % gruposRot.length;
            const grupo = gruposRot[idx];
            const row = vagasData.find(v => normalizeGroupId(v.Grupo) === grupo);
            const hist = appData.historico[grupo] || [];
            newHTML += buildCardHTML(cat, grupo, row, hist, false, currentIdx);
            chartsToRender.push({ lineId: `chart-line-${cat}-${currentIdx}`, barId: `chart-bar-${cat}-${currentIdx}`, hist, color: COLORS[cat] });
            currentIdx++;
        }
        const total = gruposRot.length;
        const start = (rotIndex[cat] % total) + 1;
        const end = Math.min(start + regularSlots - 1, total);
        const shown = Array.from({ length: regularSlots }, (_, i) => gruposRot[(rotIndex[cat] + i) % total]);
        const favPrefix = favs.length > 0 ? `Fav: ${favs[0]} | ` : '';
        document.getElementById(`prog-${cat}`).innerText = `${favPrefix}${start}-${end} / ${total} (${shown.join(' · ')})`;
    } else {
        document.getElementById(`prog-${cat}`).innerText = favs.length > 0 ? `Fav: ${favs[0]}` : '';
    }

    const doRender = () => {
        container.innerHTML = newHTML;
        // Forçar reflow para ativar animação CSS
        container.querySelectorAll('.card').forEach((card, i) => {
            card.style.animationDelay = `${i * 80}ms`;
            card.classList.add('card-entering');
        });
        setTimeout(() => chartsToRender.forEach(c => renderChartPair(c.lineId, c.barId, c.hist, c.color)), 80);
    };

    if (animate && container.children.length > 0) {
        // Fade out cards rotativos (não o favorito - índice 0 se existir)
        const rotCards = favs.length > 0
            ? Array.from(container.children).slice(1)
            : Array.from(container.children);
        rotCards.forEach(card => card.classList.add('card-leaving'));
        setTimeout(doRender, 380);
    } else {
        doRender();
    }
};

const overrideStyle = document.createElement('style');
overrideStyle.textContent = `
    .cfg-manual-fav { margin-bottom:12px; padding:10px; border:1px solid var(--border); border-radius:8px; background:rgba(26,36,64,0.55); }
    .cfg-manual-title { font-size:12px; font-weight:bold; color:var(--gold); margin-bottom:6px; text-transform:uppercase; letter-spacing:0.7px; }
    .cfg-manual-row { display:flex; gap:8px; }
    .cfg-manual-desc { margin-top:6px; font-size:11px; color:var(--text2); }
    .cfg-rotation-box { margin-top:10px; padding:10px 12px; border:1px solid var(--border); border-radius:8px; background:rgba(10,14,26,0.55); font-size:12px; color:var(--text2); line-height:1.6; }

    /* Transições suaves de cards */
    .card {
        transition: opacity 0.35s ease, transform 0.35s ease;
    }
    .card-entering {
        animation: cardEnter 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
    }
    @keyframes cardEnter {
        from { opacity: 0; transform: translateY(18px) scale(0.98); }
        to   { opacity: 1; transform: translateY(0)   scale(1);    }
    }
    .card-leaving {
        animation: cardLeave 0.35s ease-in forwards;
        pointer-events: none;
    }
    @keyframes cardLeave {
        from { opacity: 1; transform: translateY(0)    scale(1);    }
        to   { opacity: 0; transform: translateY(-14px) scale(0.97); }
    }

    .chart-panel { animation: chartPanelFade 0.45s ease-out; }
    @keyframes chartPanelFade {
        from { opacity:0; transform:translateY(8px); }
        to { opacity:1; transform:translateY(0); }
    }
`;
document.head.appendChild(overrideStyle);


fetchData();
setInterval(fetchData, 15000);

