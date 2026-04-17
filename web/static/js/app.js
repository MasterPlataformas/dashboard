const COLORS = {
    auto: '#FF1212',
    imovel: '#FF1212',
    pesado: '#FF1212',
    gold: '#FF1212',
    green: '#4CAF50',
    white: '#FFFFFF',
    bg3: '#141C30',
    bg4: '#1A2440',
    navy: '#0D1B3E',
    border: '#1E2D50',
    plotBg: '#10192C',
    plotGrid: '#22304F',
    text: '#E0E8FF',
    text2: '#8899BB',
    text3: '#556080'
};

let appData = {
    vagas: { auto: [], imovel: [], pesado: [] },
    historico: {},
    config: {}
};

let rotIndex = { auto: 0, imovel: 0, pesado: 0 };
let chartInstances = {};

const valueLabelsPlugin = {
    id: 'valueLabels',
    afterDatasetsDraw(chart, args, pluginOptions) {
        if (!pluginOptions || pluginOptions.enabled === false) return;

        const { ctx } = chart;
        ctx.save();

        chart.data.datasets.forEach((dataset, datasetIndex) => {
            const meta = chart.getDatasetMeta(datasetIndex);
            if (meta.hidden) return;

            meta.data.forEach((element, index) => {
                const rawValue = dataset.data[index];
                if (rawValue === null || rawValue === undefined || Number.isNaN(rawValue)) return;

                const pos = element.tooltipPosition();
                const isBar = (dataset.type || meta.type || chart.config.type) === 'bar';
                const offsetY = isBar ? -10 : (dataset.label === 'Min' ? 14 : -12);
                const formatted = isBar ? String(Math.round(Number(rawValue))) : Number(rawValue).toFixed(1);

                ctx.font = "bold 11px 'Segoe UI'";
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = dataset.label === 'Min'
                    ? COLORS.white
                    : (dataset.borderColor || dataset.backgroundColor || COLORS.text);
                ctx.fillText(formatted, pos.x, pos.y + offsetY);
            });
        });

        ctx.restore();
    }
};

function destroyChart(id) {
    if (chartInstances[id]) {
        chartInstances[id].destroy();
        delete chartInstances[id];
    }
}

function updateTime() {
    const now = new Date();
    document.getElementById('clock').innerText = now.toLocaleTimeString('pt-BR');

    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    let dateStr = now.toLocaleDateString('pt-BR', options);
    dateStr = dateStr.charAt(0).toUpperCase() + dateStr.slice(1);
    document.getElementById('date').innerText = dateStr;
}

setInterval(updateTime, 1000);
updateTime();

async function fetchData() {
    try {
        const response = await fetch('/api/data');
        if (!response.ok) throw new Error('Network response was not ok');

        const data = await response.json();
        appData = data;

        const rt = data.config.real_time ? ' (tempo real)' : '';
        const numGrupos = Object.keys(data.historico).length;
        document.getElementById('status-bar').innerHTML =
            `✔ Atualizado ${new Date().toLocaleTimeString('pt-BR')}${rt} | Histórico: ${numGrupos} grupos`;

        renderAllColumns();
    } catch (error) {
        console.error('Erro buscando dados:', error);
        document.getElementById('status-bar').innerHTML = `Erro de conexão: ${error.message}`;
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
        if (tail.length === 0) return { med: '—', cont: '—' };

        const sumMin = tail.reduce((sum, row) => sum + Number(row.Lance_Min), 0);
        const sumMax = tail.reduce((sum, row) => sum + Number(row.Lance_Max), 0);
        const med = `${((sumMin + sumMax) / (2 * tail.length)).toFixed(2)}%`;
        const cont = tail.reduce((sum, row) => sum + Number(row.QT_Contemp), 0);

        return { med, cont };
    };

    const s12 = getStats(12);
    const s6 = getStats(6);
    const s3 = getStats(3);

    return `
        <table class="summary-table">
            <tr>
                <th style="color: ${color}">Período</th>
                <th style="color: ${color}">Média %</th>
                <th style="color: ${color}">Contemp.</th>
            </tr>
            <tr>
                <td style="color: ${COLORS.text2}">12m</td>
                <td style="color: ${s12.med !== '—' ? color : COLORS.text3}">${s12.med}</td>
                <td style="color: ${s12.cont !== '—' ? COLORS.green : COLORS.text3}">${s12.cont}</td>
            </tr>
            <tr>
                <td style="color: ${COLORS.text2}">6m</td>
                <td style="color: ${s6.med !== '—' ? color : COLORS.text3}">${s6.med}</td>
                <td style="color: ${s6.cont !== '—' ? COLORS.green : COLORS.text3}">${s6.cont}</td>
            </tr>
            <tr>
                <td style="color: ${COLORS.text2}">3m</td>
                <td style="color: ${s3.med !== '—' ? color : COLORS.text3}">${s3.med}</td>
                <td style="color: ${s3.cont !== '—' ? COLORS.green : COLORS.text3}">${s3.cont}</td>
            </tr>
        </table>
    `;
}

function formatMonth(dateStr) {
    const pt = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
    const d = new Date(dateStr);
    d.setMinutes(d.getMinutes() + d.getTimezoneOffset());
    return `${pt[d.getMonth()]}/${String(d.getFullYear()).slice(-2)}`;
}

function drawEmptyChart(canvasId, label) {
    destroyChart(canvasId);

    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.font = "italic 14px 'Segoe UI'";
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
    const media3m = tail3.reduce((sum, row) => {
        return sum + ((Number(row.Lance_Min) + Number(row.Lance_Max)) / 2);
    }, 0) / tail3.length;

    return {
        media,
        media3m,
        min: Number(last.Lance_Min),
        max: Number(last.Lance_Max),
        cont: Number(last.QT_Contemp),
        periodo: formatMonth(last.Mes)
    };
}

function renderChartPair(lineCanvasId, barCanvasId, histData, color) {
    destroyChart(lineCanvasId);
    destroyChart(barCanvasId);

    if (!histData || histData.length === 0) {
        drawEmptyChart(lineCanvasId, 'Sem histórico');
        drawEmptyChart(barCanvasId, 'Sem histórico');
        return;
    }

    const sorted = [...histData].sort((a, b) => new Date(a.Mes) - new Date(b.Mes)).slice(-12);
    const labels = sorted.map((row) => formatMonth(row.Mes));
    const dataMin = sorted.map((row) => Number(row.Lance_Min));
    const dataMax = sorted.map((row) => Number(row.Lance_Max));
    const dataCont = sorted.map((row) => Number(row.QT_Contemp));

    const minY = Math.min(...dataMin);
    const maxY = Math.max(...dataMax);
    const maxCont = Math.max(...dataCont, 0);

    const sharedPlugins = {
        legend: { display: false },
        tooltip: {
            backgroundColor: 'rgba(20, 28, 48, 0.95)',
            titleColor: COLORS.white,
            bodyColor: COLORS.white,
            borderColor: COLORS.border,
            borderWidth: 1
        }
    };

    chartInstances[lineCanvasId] = new Chart(document.getElementById(lineCanvasId).getContext('2d'), {
        type: 'line',
        plugins: [valueLabelsPlugin],
        data: {
            labels,
            datasets: [
                {
                    label: 'Max',
                    data: dataMax,
                    borderColor: color,
                    backgroundColor: color,
                    borderWidth: 2.5,
                    pointBackgroundColor: COLORS.bg3,
                    pointBorderColor: color,
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    fill: false,
                    tension: 0.15
                },
                {
                    label: 'Min',
                    data: dataMin,
                    borderColor: COLORS.white,
                    backgroundColor: COLORS.white,
                    borderWidth: 2.2,
                    pointBackgroundColor: COLORS.bg3,
                    pointBorderColor: COLORS.white,
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    fill: {
    			target: '-1',
   		 	above: `${color}33`,
			below: 'transparent'
},
                    },
                    tension: 0.15
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            layout: {
                padding: { top: 20, right: 8, bottom: 0, left: 0 }
            },
            plugins: {
                ...sharedPlugins,
                valueLabels: { enabled: labels.length <= 8 }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        color: COLORS.text2,
                        autoSkip: false,
                        maxRotation: 0,
                        minRotation: 0,
                        font: { size: 11 }
                    }
                },
                y: {
                    beginAtZero: false,
                    suggestedMin: minY - 1.6,
                    suggestedMax: maxY + 1.9,
                    title: {
                        display: true,
                        text: '%',
                        color: COLORS.text2,
                        font: { size: 11 }
                    },
                    grid: {
                        color: COLORS.plotGrid,
                        borderDash: [3, 3]
                    },
                    ticks: {
                        color: COLORS.text2,
                        font: { size: 11 }
                    }
                }
            }
        }
    });

    chartInstances[barCanvasId] = new Chart(document.getElementById(barCanvasId).getContext('2d'), {
        type: 'bar',
        plugins: [valueLabelsPlugin],
        data: {
            labels,
            datasets: [
                {
                    label: 'Contemplações',
                    data: dataCont,
                    backgroundColor: `${color}DD`,
                    borderWidth: 0,
                    barThickness: Math.max(12, Math.min(22, Math.floor(140 / Math.max(labels.length, 1))))
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            layout: {
                padding: { top: 20, right: 0, bottom: 0, left: 0 }
            },
            plugins: {
                ...sharedPlugins,
                valueLabels: { enabled: true }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        color: COLORS.text2,
                        autoSkip: false,
                        maxRotation: 0,
                        minRotation: 0,
                        font: { size: 11 }
                    }
                },
                y: {
                    beginAtZero: true,
                    suggestedMax: maxCont > 0 ? maxCont * 1.28 : 1,
                    ticks: {
                        color: COLORS.text2,
                        stepSize: 1,
                        precision: 0,
                        font: { size: 11 }
                    },
                    grid: {
                        color: COLORS.plotGrid,
                        borderDash: [3, 3]
                    }
                }
            }
        }
    });
}

function renderHighlights(histData, color) {
    const metrics = getHistoryMetrics(histData);
    if (!metrics) {
        return `
            <div class="card-highlights">
                <div class="highlight-box">
                    <div class="hl-title">Histórico</div>
                    <div class="hl-val" style="color: ${COLORS.text3}">Sem dados</div>
                    <div class="hl-desc">Configure o arquivo de histórico</div>
                </div>
            </div>`;
    }

    const delta = metrics.media - metrics.media3m;
    let deltaTxt = 'Estável vs 3m';
    if (Math.abs(delta) >= 0.05) {
        deltaTxt = `${delta > 0 ? 'Acima' : 'Abaixo'} ${Math.abs(delta).toFixed(2)}% vs 3m`;
    }

    return `
        <div class="card-highlights">
            <div class="highlight-box">
                <div class="hl-title">Lance médio</div>
                <div class="hl-val" style="color: ${color}">${metrics.media.toFixed(2)}%</div>
                <div class="hl-desc">${deltaTxt}</div>
            </div>
            <div class="highlight-box" style="background-color: var(--navy)">
                <div class="hl-title">Faixa do mês</div>
                <div class="hl-val" style="color: var(--white)">${metrics.min.toFixed(1)}% a ${metrics.max.toFixed(1)}%</div>
                <div class="hl-desc">Min e max do último fechamento</div>
            </div>
            <div class="highlight-box">
                <div class="hl-title">Contemplações</div>
                <div class="hl-val" style="color: ${color}">${metrics.cont}</div>
                <div class="hl-desc">Média 3m: ${metrics.media3m.toFixed(2)}%</div>
            </div>
        </div>
    `;
}

function buildCardHTML(cat, grupo, vagaRow, histData, isFav, idx) {
    const cardClass = isFav ? 'card-fav' : `card-${cat}`;
    const mainColor = isFav ? COLORS.gold : COLORS[cat];
    const lineCanvasId = `chart-line-${cat}-${idx}`;
    const barCanvasId = `chart-bar-${cat}-${idx}`;
    const metrics = getHistoryMetrics(histData);
    const baseLabel = metrics ? `Base: ${metrics.periodo}` : 'Sem dados históricos';

    let disponivelHTML = '';
    if (vagaRow) {
        const cMin = vagaRow['Crédito mínimo'] || vagaRow['CrÃ©dito mÃ­nimo'] || vagaRow['Credito minimo'] || '—';
        const cMax = vagaRow['Crédito máximo'] || vagaRow['CrÃ©dito mÃ¡ximo'] || vagaRow['Credito maximo'] || '—';
        const valParcela = vagaRow['Valor médio parcela'] || vagaRow['Valor mÃ©dio parcela'] || '—';
        const meses = vagaRow['Meses restantes'] || '—';
        const vagasLivres = vagaRow._vagas_livres ?? '—';

        disponivelHTML = `
            <div class="card-info">
                <div class="info-item">
                    <span class="info-label">Crédito</span>
                    <span class="info-val">${cMin} → ${cMax}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Parcela</span>
                    <span class="info-val">${valParcela}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Prazo</span>
                    <span class="info-val">${meses}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Vagas livres</span>
                    <span class="info-val">${vagasLivres}</span>
                </div>
            </div>
        `;
    } else {
        disponivelHTML = `
            <div class="card-info">
                <span style="color: var(--orange); font-size: 11px; font-style: italic;">
                    Grupo indisponível no momento
                </span>
            </div>
        `;
    }

    return `
        <div class="card ${cardClass}">
            <div class="card-header">
                <div class="card-group">
                    <span class="card-group-label">GRUPO</span>
                    <span class="card-group-val">${grupo}</span>
                </div>
                ${disponivelHTML}
                <div class="card-table">
                    ${renderSummaryTable(histData, mainColor)}
                </div>
            </div>
            ${renderHighlights(histData, mainColor)}
            <div class="card-chart">
                <div class="chart-head">
                    <div class="chart-head-title">Histórico de lances em destaque</div>
                    <div class="chart-head-base">${baseLabel}</div>
                </div>
                <div class="chart-grid">
                    <div class="chart-panel chart-panel-line">
                        <div class="chart-title">Histórico de Lances (%)</div>
                        <canvas id="${lineCanvasId}"></canvas>
                    </div>
                    <div class="chart-panel chart-panel-bar">
                        <div class="chart-title">Contemplações</div>
                        <canvas id="${barCanvasId}"></canvas>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderColumn(cat) {
    const colConfig = appData.config[cat] || {};
    const vagasData = appData.vagas[cat] || [];

    let favs = colConfig.favoritos || [];
    if (typeof favs === 'string') favs = favs.split('\n');

    const vagasSimul = colConfig.vagas_simultaneas || 2;
    const gruposRot = vagasData.map((vaga) => vaga.Grupo).filter((grupo) => !favs.includes(grupo));

    const container = document.getElementById(`cards-${cat}`);
    container.innerHTML = '';
    const chartsToRender = [];
    let currentIdx = 0;

    if (favs.length > 0) {
        const grupo = favs[0];
        const row = vagasData.find((vaga) => vaga.Grupo === grupo);
        const hist = appData.historico[grupo] || [];

        container.innerHTML += buildCardHTML(cat, grupo, row, hist, true, currentIdx);
        chartsToRender.push({
            lineId: `chart-line-${cat}-${currentIdx}`,
            barId: `chart-bar-${cat}-${currentIdx}`,
            hist,
            color: COLORS.gold
        });
        currentIdx += 1;
    }

    if (gruposRot.length > 0) {
        const startIdx = rotIndex[cat];

        for (let i = 0; i < vagasSimul; i += 1) {
            const idx = (startIdx + i) % gruposRot.length;
            const grupo = gruposRot[idx];
            const row = vagasData.find((vaga) => vaga.Grupo === grupo);
            const hist = appData.historico[grupo] || [];

            container.innerHTML += buildCardHTML(cat, grupo, row, hist, false, currentIdx);
            chartsToRender.push({
                lineId: `chart-line-${cat}-${currentIdx}`,
                barId: `chart-bar-${cat}-${currentIdx}`,
                hist,
                color: COLORS[cat]
            });
            currentIdx += 1;
        }

        const total = gruposRot.length;
        const start = (startIdx % total) + 1;
        const end = Math.min(start + vagasSimul - 1, total);
        const shown = Array.from({ length: vagasSimul }, (_, i) => gruposRot[(startIdx + i) % total]);
        document.getElementById(`prog-${cat}`).innerText = `${start}-${end} / ${total} (${shown.join(' · ')})`;
    } else {
        for (let i = 0; i < vagasSimul; i += 1) {
            container.innerHTML += buildCardHTML(cat, '---', null, [], false, currentIdx);
            chartsToRender.push({
                lineId: `chart-line-${cat}-${currentIdx}`,
                barId: `chart-bar-${cat}-${currentIdx}`,
                hist: [],
                color: COLORS[cat]
            });
            currentIdx += 1;
        }

        document.getElementById(`prog-${cat}`).innerText = '';
    }

    setTimeout(() => {
        chartsToRender.forEach((chart) => {
            renderChartPair(chart.lineId, chart.barId, chart.hist, chart.color);
        });
    }, 50);
}

function renderAllColumns() {
    renderColumn('auto');
    renderColumn('imovel');
    renderColumn('pesado');
}

function toggleControlPanel() {
    const modal = document.getElementById('control-panel');
    modal.style.display = modal.style.display === 'block' ? 'none' : 'block';
    if (modal.style.display === 'block') {
        pollStatus();
    }
}

async function startExtraction() {
    const user = document.getElementById('ext-user').value;
    const pass = document.getElementById('ext-pass').value;
    const btn = document.getElementById('btn-start-ext');

    try {
        btn.disabled = true;
        btn.innerText = 'Iniciando...';

        const response = await fetch('/api/extrair', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ usuario: user, senha: pass })
        });

        const result = await response.json();
        if (response.ok) {
            pollStatus();
        } else {
            alert(`Erro: ${result.error || 'Falha ao iniciar extração'}`);
            btn.disabled = false;
            btn.innerText = 'Iniciar nova extração';
        }
    } catch (error) {
        alert(`Erro de conexão: ${error.message}`);
        btn.disabled = false;
        btn.innerText = 'Iniciar nova extração';
    }
}

let statusInterval = null;

async function pollStatus() {
    if (statusInterval) return;

    statusInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/status');
            const status = await response.json();

            const dot = document.getElementById('ext-status-dot');
            const text = document.getElementById('ext-status-text');
            const log = document.getElementById('ext-log');
            const progress = document.getElementById('ext-progress-bar');
            const btn = document.getElementById('btn-start-ext');

            if (status.rodando) {
                dot.classList.add('active');
                text.innerText = 'Extraindo dados...';
                btn.disabled = true;
                btn.innerText = 'Extração em andamento...';
            } else {
                dot.classList.remove('active');
                text.innerText = 'Aguardando início...';
                btn.disabled = false;
                btn.innerText = 'Iniciar nova extração';

                if (status.progresso === 100) {
                    fetchData();
                }
            }

            log.innerText = status.ultimo_log || '---';
            progress.style.width = `${status.progresso}%`;
            progress.innerText = `${status.progresso}%`;

            const modal = document.getElementById('control-panel');
            if (modal.style.display !== 'block' && !status.rodando) {
                clearInterval(statusInterval);
                statusInterval = null;
            }
        } catch (error) {
            console.error('Erro no poll de status:', error);
        }
    }, 2000);
}

fetchData();

setInterval(() => {
    ['auto', 'imovel', 'pesado'].forEach((cat) => {
        const colConfig = appData.config[cat] || {};
        const vagasSimul = colConfig.vagas_simultaneas || 2;
        rotIndex[cat] += vagasSimul;
        renderColumn(cat);
    });
}, 12000);

setInterval(fetchData, 15000);
