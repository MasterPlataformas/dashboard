// Cores e configuração
const COLORS = {
    auto: '#60A7EA',
    imovel: '#FF1212',
    pesado: '#D849FC',
    gold: '#FFB300',
    green: '#4CAF50',
    bg3: '#141C30',
    text: '#E0E8FF'
};

let appData = {
    vagas: { auto: [], imovel: [], pesado: [] },
    historico: {},
    config: {}
};

let rotIndex = { auto: 0, imovel: 0, pesado: 0 };
let chartInstances = {};

// Relógio e Data
function updateTime() {
    const now = new Date();
    document.getElementById('clock').innerText = now.toLocaleTimeString('pt-BR');
    
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    let dateStr = now.toLocaleDateString('pt-BR', options);
    // Capitalizar primeira letra
    dateStr = dateStr.charAt(0).toUpperCase() + dateStr.slice(1);
    document.getElementById('date').innerText = dateStr;
}
setInterval(updateTime, 1000);
updateTime();

// Buscar dados da API
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
        document.getElementById('status-bar').innerHTML = `❌ Erro de conexão: ${error.message}`;
    }
}

// Renderizar Tabela Resumo (3m, 6m, 12m)
function renderSummaryTable(histData, color) {
    if (!histData || histData.length === 0) {
        return `<table class="summary-table">
            <tr><th>Período</th><th>Média %</th><th>Contemp.</th></tr>
            <tr><td>12m</td><td>—</td><td>—</td></tr>
            <tr><td>6m</td><td>—</td><td>—</td></tr>
            <tr><td>3m</td><td>—</td><td>—</td></tr>
        </table>`;
    }
    
    // histData já deve vir ordenado do Python, vamos garantir
    const sorted = [...histData].sort((a, b) => new Date(a.Mes) - new Date(b.Mes));
    
    const getStats = (n) => {
        const tail = sorted.slice(-n);
        if (tail.length === 0) return { med: '—', cont: '—' };
        const sumMin = tail.reduce((sum, r) => sum + r.Lance_Min, 0);
        const sumMax = tail.reduce((sum, r) => sum + r.Lance_Max, 0);
        const med = ((sumMin + sumMax) / (2 * tail.length)).toFixed(2) + '%';
        const cont = tail.reduce((sum, r) => sum + r.QT_Contemp, 0);
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
                <td style="color: #8899BB">12m</td>
                <td style="color: ${s12.med !== '—' ? color : '#556080'}">${s12.med}</td>
                <td style="color: ${s12.cont !== '—' ? COLORS.green : '#556080'}">${s12.cont}</td>
            </tr>
            <tr>
                <td style="color: #8899BB">6m</td>
                <td style="color: ${s6.med !== '—' ? color : '#556080'}">${s6.med}</td>
                <td style="color: ${s6.cont !== '—' ? COLORS.green : '#556080'}">${s6.cont}</td>
            </tr>
            <tr>
                <td style="color: #8899BB">3m</td>
                <td style="color: ${s3.med !== '—' ? color : '#556080'}">${s3.med}</td>
                <td style="color: ${s3.cont !== '—' ? COLORS.green : '#556080'}">${s3.cont}</td>
            </tr>
        </table>
    `;
}

// Formatador de meses (ex: "jan/23")
function formatMonth(dateStr) {
    const pt = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
    const d = new Date(dateStr);
    // Adicionar timezone offset senao a data pode voltar 1 dia
    d.setMinutes(d.getMinutes() + d.getTimezoneOffset());
    return `${pt[d.getMonth()]}/${String(d.getFullYear()).slice(-2)}`;
}

// Renderizar Gráfico com Chart.js
function renderChart(canvasId, histData, color) {
    if (chartInstances[canvasId]) {
        chartInstances[canvasId].destroy();
    }

    if (!histData || histData.length === 0) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        ctx.font = "italic 14px 'Segoe UI'";
        ctx.fillStyle = "#556080";
        ctx.textAlign = "center";
        ctx.fillText("Sem histórico", 300, 75);
        return;
    }

    // Pegar últimos 12 meses
    const sorted = [...histData].sort((a, b) => new Date(a.Mes) - new Date(b.Mes)).slice(-12);
    
    const labels = sorted.map(r => formatMonth(r.Mes));
    const dataMin = sorted.map(r => r.Lance_Min);
    const dataMax = sorted.map(r => r.Lance_Max);
    const dataCont = sorted.map(r => r.QT_Contemp);

    const ctx = document.getElementById(canvasId).getContext('2d');
    
    chartInstances[canvasId] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Max',
                    data: dataMax,
                    borderColor: color,
                    backgroundColor: color,
                    borderWidth: 2,
                    pointBackgroundColor: COLORS.bg3,
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    yAxisID: 'y',
                    fill: false,
                    tension: 0.1
                },
                {
                    label: 'Min',
                    data: dataMin,
                    borderColor: COLORS.text,
                    backgroundColor: COLORS.text,
                    borderWidth: 2,
                    pointBackgroundColor: COLORS.bg3,
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    yAxisID: 'y',
                    fill: {
                        target: '-1',
                        above: color + '33' // 20% opacity do acc color para preencher área entre min/max
                    },
                    tension: 0.1
                },
                {
                    label: 'Contemp',
                    type: 'bar',
                    data: dataCont,
                    backgroundColor: color + 'DD',
                    yAxisID: 'y1',
                    barThickness: 15
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(20, 28, 48, 0.9)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: '#1E2D50',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: COLORS.text2, font: { size: 10 } }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: { display: true, text: 'Lance (%)', color: COLORS.text2, font: { size: 10 } },
                    grid: { color: '#1A2540', borderDash: [2, 4] },
                    ticks: { color: COLORS.text2, font: { size: 10 } }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: { display: true, text: 'Contemplações', color: COLORS.text2, font: { size: 10 } },
                    grid: { display: false },
                    ticks: { color: COLORS.text2, font: { size: 10 }, stepSize: 1 }
                }
            }
        }
    });
}

// Highlights Histórico (v2)
function renderHighlights(histData, color) {
    if (!histData || histData.length === 0) {
        return `
            <div class="card-highlights">
                <div class="highlight-box">
                    <div class="hl-title">Histórico</div>
                    <div class="hl-val" style="color: #556080">Sem dados</div>
                    <div class="hl-desc">Configure o arquivo de histórico</div>
                </div>
            </div>`;
    }

    const sorted = [...histData].sort((a, b) => new Date(a.Mes) - new Date(b.Mes));
    const last = sorted[sorted.length - 1];
    const tail3 = sorted.slice(-3);
    
    const media = (last.Lance_Min + last.Lance_Max) / 2;
    const media3m = tail3.reduce((sum, r) => sum + (r.Lance_Min + r.Lance_Max)/2, 0) / tail3.length;
    
    const delta = media - media3m;
    let deltaTxt = 'Estável vs 3m';
    if (Math.abs(delta) >= 0.05) {
        deltaTxt = `${delta > 0 ? 'Acima' : 'Abaixo'} ${Math.abs(delta).toFixed(2)}% vs 3m`;
    }

    return `
        <div class="card-highlights">
            <div class="highlight-box">
                <div class="hl-title">Lance médio</div>
                <div class="hl-val" style="color: ${color}">${media.toFixed(2)}%</div>
                <div class="hl-desc">${deltaTxt}</div>
            </div>
            <div class="highlight-box" style="background-color: var(--navy)">
                <div class="hl-title">Faixa do mês</div>
                <div class="hl-val" style="color: var(--white)">${last.Lance_Min.toFixed(1)}% a ${last.Lance_Max.toFixed(1)}%</div>
                <div class="hl-desc">Min e max do último fechamento</div>
            </div>
            <div class="highlight-box">
                <div class="hl-title">Contemplações</div>
                <div class="hl-val" style="color: ${color}">${last.QT_Contemp}</div>
                <div class="hl-desc">Média 3m: ${media3m.toFixed(2)}%</div>
            </div>
        </div>
    `;
}

// Construir Card
function buildCardHTML(cat, grupo, vagaRow, histData, isFav, idx) {
    const cardClass = isFav ? 'card-fav' : `card-${cat}`;
    const mainColor = isFav ? COLORS.gold : COLORS[cat];
    const canvasId = `chart-${cat}-${idx}`;

    let disponivelHTML = '';
    if (vagaRow) {
        const cMin = vagaRow['Crédito mínimo'] || vagaRow['Crédito mínimo']; // lida c encoding q vem do back
        const cMax = vagaRow['Crédito máximo'];
        const valParcela = vagaRow['Valor médio parcela'];
        const meses = vagaRow['Meses restantes'];
        const vagasLivres = vagaRow['_vagas_livres'];
        
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
                <canvas id="${canvasId}"></canvas>
            </div>
        </div>
    `;
}

function renderColumn(cat) {
    const colConfig = appData.config[cat] || {};
    const vagasData = appData.vagas[cat] || [];
    
    let favs = colConfig.favoritos || [];
    if (typeof favs === 'string') favs = favs.split('\\n'); // se vier torto

    const vagasSimul = colConfig.vagas_simultaneas || 2;
    
    // Filtrar grupos pra rotacao (que nao estao nos favoritos)
    const gruposRot = vagasData.map(v => v.Grupo).filter(g => !favs.includes(g));
    
    const container = document.getElementById(`cards-${cat}`);
    container.innerHTML = '';
    const chartsToRender = [];

    let totalCards = (favs.length > 0 ? 1 : 0) + vagasSimul;
    let currentIdx = 0;

    if (favs.length > 0) {
        const g = favs[0];
        const row = vagasData.find(v => v.Grupo === g);
        const hist = appData.historico[g] || [];
        container.innerHTML += buildCardHTML(cat, g, row, hist, true, currentIdx);
        chartsToRender.push({ id: `chart-${cat}-${currentIdx}`, hist: hist, color: COLORS.gold });
        currentIdx++;
    }

    if (gruposRot.length > 0) {
        const startIdx = rotIndex[cat];
        
        for (let i = 0; i < vagasSimul; i++) {
            const idx = (startIdx + i) % gruposRot.length;
            const g = gruposRot[idx];
            const row = vagasData.find(v => v.Grupo === g);
            const hist = appData.historico[g] || [];
            
            container.innerHTML += buildCardHTML(cat, g, row, hist, false, currentIdx);
            chartsToRender.push({ id: `chart-${cat}-${currentIdx}`, hist: hist, color: COLORS[cat] });
            currentIdx++;
        }
        
        // Update progress label
        const total = gruposRot.length;
        const s = (startIdx % total) + 1;
        const e = Math.min(s + vagasSimul - 1, total);
        const shown = Array.from({length: vagasSimul}, (_, i) => gruposRot[(startIdx + i) % total]);
        document.getElementById(`prog-${cat}`).innerText = `${s}-${e} / ${total} (${shown.join(' · ')})`;
    } else {
        for (let i = 0; i < vagasSimul; i++) {
            container.innerHTML += buildCardHTML(cat, '---', null, [], false, currentIdx);
            chartsToRender.push({ id: `chart-${cat}-${currentIdx}`, hist: [], color: COLORS[cat] });
            currentIdx++;
        }
        document.getElementById(`prog-${cat}`).innerText = ``;
    }

    // Render charts
    setTimeout(() => {
        chartsToRender.forEach(c => renderChart(c.id, c.hist, c.color));
    }, 50);
}

function renderAllColumns() {
    renderColumn('auto');
    renderColumn('imovel');
    renderColumn('pesado');
}

// Controle do Painel
function toggleControlPanel() {
    const modal = document.getElementById('control-panel');
    modal.style.display = (modal.style.display === 'block') ? 'none' : 'block';
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
        btn.innerText = '⌛ Iniciando...';

        const response = await fetch('/api/extrair', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ usuario: user, senha: pass })
        });

        const result = await response.json();
        if (response.ok) {
            pollStatus();
        } else {
            alert('Erro: ' + (result.error || 'Falha ao iniciar extração'));
            btn.disabled = false;
            btn.innerText = '🚀 Iniciar Nova Extração';
        }
    } catch (error) {
        alert('Erro de conexão: ' + error.message);
        btn.disabled = false;
        btn.innerText = '🚀 Iniciar Nova Extração';
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
                btn.innerText = '⌛ Extração em andamento...';
            } else {
                dot.classList.remove('active');
                text.innerText = 'Aguardando início...';
                btn.disabled = false;
                btn.innerText = '🚀 Iniciar Nova Extração';
                
                // Se parou de rodar e estava rodando, buscar novos dados
                if (status.progresso === 100) {
                    fetchData(); 
                }
            }

            log.innerText = status.ultimo_log || '---';
            progress.style.width = status.progresso + '%';
            progress.innerText = status.progresso + '%';

            // Parar de poll se fechar o modal e não estiver rodando
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

// Inicializacao e Rotação
fetchData();

// Rotação: Atualiza o index e re-renderiza sem buscar novos dados
setInterval(() => {
    ['auto', 'imovel', 'pesado'].forEach(cat => {
        const colConfig = appData.config[cat] || {};
        const vagasSimul = colConfig.vagas_simultaneas || 2;
        rotIndex[cat] += vagasSimul;
        renderColumn(cat);
    });
}, 12000); // 12s de rotação

// Recarregar os dados do backend
setInterval(fetchData, 15000); // Polling frequente para detectar mudanças
