"""
Dashboard Master Prime – Automóveis · Imóveis · Veículos Pesados
Tema escuro azul-preto, 3 colunas.
Layout: 1 favorito + 2 rotativos com tamanhos iguais (grid).
Recursos: Zoom da interface (0.7 a 1.5), atualização em tempo real (polling 2s),
          filtro de vagas livres corrigido (máximo de vagas disponíveis).
Botão de fechar vermelho incluso.
Seleção de monitor (primário/secundário) via Painel de Controle.
"""

import tkinter as tk
try:
    import tkinter.filedialog as filedialog
except Exception:
    filedialog = None
from tkinter import ttk, messagebox
import pandas as pd
from datetime import datetime
import json, os, traceback
import re
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Impede o matplotlib de criar janelas Tk fantasmas em segundo plano
plt.ioff()   # desativa modo interativo – sem janelas automáticas
import ctypes
from ctypes import wintypes

# ══════════════════════════════════════════════════════════════════════════════
# PALETA – tema escuro azul-preto
# ══════════════════════════════════════════════════════════════════════════════
C = {
    'bg':          '#0A0E1A',
    'bg2':         '#0F1525',
    'bg3':         '#141C30',
    'bg4':         '#1A2440',
    'navy':        '#0D1B3E',
    'blue':        '#1A3A6B',
    'blue_l':      '#2B5BA8',
    'cyan':        '#4FC3F7',
    'orange':      '#FF6B2B',
    'gold':        '#FFB300',
    'green':       '#4CAF50',
    'green_l':     '#1B3A1D',
    'red_l':       '#3A1A0A',
    'white':       '#FFFFFF',
    'text':        '#E0E8FF',
    'text2':       '#8899BB',
    'text3':       '#556080',
    'border':      '#1E2D50',
    'tbl_h':       '#162040',
    'tbl_alt':     '#111827',
    'plot_bg':     '#0D1525',
    'plot_grid':   '#1A2540',
    'auto_acc':    "#60A7EA",
    'imovel_acc':  "#FF1212",
    'pesado_acc':  "#D849FC",
}

FONT = 'Segoe UI'

FAIXAS = {
    'auto':   ['25000-50000', '34000-65000', '62500-125000', '125000-200000'],
    'imovel': ['70000-140000', '140000-280000', '280000-560000', '600000-900000', '900000-1000000'],
    'pesado': ['180000-360000'],
}
LABELS = {
    'auto':   ('🚗', 'AUTOMÓVEIS',       C['auto_acc']),
    'imovel': ('🏠', 'IMÓVEIS',          C['imovel_acc']),
    'pesado': ('🚛', 'VEÍCULOS PESADOS', C['pesado_acc']),
}

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG PERSISTENTE (incluindo monitor_index)
# ══════════════════════════════════════════════════════════════════════════════
CONFIG_FILE = 'dashboard_config.json'

def _default_cat(faixas):
    return {
        'arquivo': '',
        'favoritos': [],
        'vagas_simultaneas': 2,
        'rotacao_intervalo': 12,
        'min_meses': 0,
        'max_meses': 999,
        'max_vagas_livres': 200,
        'faixas': [],
    }

DEFAULT_CONFIG = {
    'historico':        '',
    'reload_intervalo': 300,
    'fullscreen':       True,
    'font_scale':       1.0,
    'ui_scale':         1.0,
    'real_time':        False,
    'monitor_index':    0,
    'auto':   _default_cat(FAIXAS['auto']),
    'imovel': _default_cat(FAIXAS['imovel']),
    'pesado': _default_cat(FAIXAS['pesado']),
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding='utf-8') as f:
                saved = json.load(f)
            cfg = DEFAULT_CONFIG.copy()
            for k, v in saved.items():
                if k in cfg and isinstance(cfg[k], dict) and isinstance(v, dict):
                    if 'min_vagas_livres' in v and 'max_vagas_livres' not in v:
                        v['max_vagas_livres'] = v.pop('min_vagas_livres')
                    cfg[k].update(v)
                elif k in cfg:
                    cfg[k] = v
            return cfg
        except: pass
    return {k: (v.copy() if isinstance(v, dict) else v) for k, v in DEFAULT_CONFIG.items()}

def save_config(cfg):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except: return False

CONFIG = load_config()

# ══════════════════════════════════════════════════════════════════════════════
# LEITURA DE DADOS – com filtro de vagas livres corrigido (máximo)
# ══════════════════════════════════════════════════════════════════════════════
def _find_column(df, possible_names):
    for col in df.columns:
        col_lower = col.lower().strip()
        for name in possible_names:
            if name.lower() in col_lower:
                return col
    return None

def load_vagas(path, categoria):
    frames = []
    xl = pd.ExcelFile(path)
    for sheet in FAIXAS[categoria]:
        if sheet in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet, header=0)
            df['Faixa'] = sheet
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    df_all = pd.concat(frames, ignore_index=True)

    df_all['_meses'] = df_all['Meses restantes'].astype(str).str.extract(r'(\d+)')[0].astype(float)

    vagas_col = _find_column(df_all, ['vagas/participantes', 'vagas / participantes', 'vagas', 'participantes'])
    if vagas_col is None:
        print(f"⚠️ Coluna de vagas não encontrada para {categoria}. Filtro de vagas livres desabilitado.")
        df_all['_vagas_livres'] = 999
    else:
        def calc_vagas_livres(val):
            try:
                s = str(val).strip()
                match = re.search(r'(\d+)\s*/\s*(\d+)', s)
                if match:
                    ocupadas = int(match.group(1))
                    total = int(match.group(2))
                    return total - ocupadas
            except:
                pass
            return 0
        df_all['_vagas_livres'] = df_all[vagas_col].apply(calc_vagas_livres)

    return df_all

def load_historico(path):
    def melt_sheet(xl, sheet, val):
        df = pd.read_excel(xl, sheet_name=sheet, header=3)
        cols = [c for c in df.columns if c not in ('CD_Grupo', 'Total Geral')]
        df['CD_Grupo'] = df['CD_Grupo'].astype(str).str.strip().str.upper()
        m = df[['CD_Grupo'] + cols].melt(id_vars='CD_Grupo', var_name='Mes', value_name=val)
        return m.dropna(subset=[val])
    xl = pd.ExcelFile(path)
    df = (melt_sheet(xl, 'MinPS',  'Lance_Min')
          .merge(melt_sheet(xl, 'MaxPS',  'Lance_Max'),  on=['CD_Grupo','Mes'])
          .merge(melt_sheet(xl, 'ContPS', 'QT_Contemp'), on=['CD_Grupo','Mes']))
    df['Mes'] = pd.to_datetime(df['Mes'], errors='coerce')
    df = df.dropna(subset=['Mes'])
    for c in ['Lance_Min','Lance_Max','QT_Contemp']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.dropna().sort_values('Mes')

def filtrar_vagas(df, cat):
    if df is None or df.empty:
        return pd.DataFrame()
    cfg = CONFIG[cat]
    d = df.copy()
    
    mn, mx = cfg.get('min_meses', 0), cfg.get('max_meses', 999)
    if mn > 0:
        d = d[d['_meses'] >= mn]
    if mx < 999:
        d = d[d['_meses'] <= mx]
    
    max_vagas = cfg.get('max_vagas_livres', 200)
    if max_vagas > 0 and '_vagas_livres' in d.columns:
        d['_vagas_livres'] = pd.to_numeric(d['_vagas_livres'], errors='coerce').fillna(0)
        d = d[d['_vagas_livres'] <= max_vagas]
    
    if cfg.get('faixas'):
        d = d[d['Faixa'].isin(cfg['faixas'])]
    
    return d.drop_duplicates(subset='Grupo', keep='first').reset_index(drop=True)

# ══════════════════════════════════════════════════════════════════════════════
# GRÁFICOS – últimos 4 meses, sem legenda
# ══════════════════════════════════════════════════════════════════════════════
def _fmt_m(dates):
    pt = {1:'jan',2:'fev',3:'mar',4:'abr',5:'mai',6:'jun',
          7:'jul',8:'ago',9:'set',10:'out',11:'nov',12:'dez'}
    return [f"{pt.get(d.month,'?')}/{str(d.year)[-2:]}" if hasattr(d,'month') else str(d) for d in dates]

def build_figure(hist_df, card_h_px, card_w_px, acc_color, scale):
    """
    Gráfico de histórico: até 12 meses, 2 subplots lado a lado (Lance Min/Max e Contemplações).
    Layout horizontal para máxima legibilidade com muitos meses.
    """
    N_MESES = 12  # quantos meses mostrar no histórico

    if not hist_df.empty:
        hist_df = hist_df.sort_values('Mes').tail(N_MESES)
    else:
        hist_df = hist_df.copy()

    dpi   = 96
    # Altura proporcional ao card, largura total disponível
    fig_h = max(1.4, (card_h_px - int(55 * scale)) / dpi)
    fig_w = max(4.0, card_w_px / dpi)
    # Escala de fonte: base maior para melhor legibilidade
    fs = lambda b: max(8, int(b * scale * 1.45))

    fig = plt.Figure(figsize=(fig_w, fig_h), facecolor=C['bg3'], dpi=dpi)

    # Ajuste de margens: espaço para labels no topo e eixo X embaixo
    top_gap  = 0.13
    bot_gap  = max(0.28, 32 / max(card_h_px, 1))
    fig.subplots_adjust(left=0.02, right=0.98, top=1 - top_gap,
                        bottom=bot_gap, wspace=0.10)

    ax1 = fig.add_subplot(1, 2, 1)  # Lance Mín × Máx
    ax2 = fig.add_subplot(1, 2, 2)  # Contemplações

    for ax in (ax1, ax2):
        ax.set_facecolor(C['plot_bg'])
        for sp in ax.spines.values():
            sp.set_edgecolor(C['border'])
            sp.set_linewidth(0.6)
        ax.yaxis.set_visible(False)
        ax.grid(axis='y', color=C['plot_grid'], linewidth=0.6,
                linestyle='--', zorder=0)
        ax.tick_params(colors=C['text2'], labelsize=fs(7), length=2, pad=2)

    # Títulos dos subgráficos
    fig.text(0.25, 1 - top_gap / 2, 'Lance Min x Max  (%)',
             ha='center', va='center', color=C['text'],
             fontsize=fs(9), fontweight='bold', fontfamily=FONT)
    fig.text(0.75, 1 - top_gap / 2, 'Contemplacoes por Lance',
             ha='center', va='center', color=C['text'],
             fontsize=fs(9), fontweight='bold', fontfamily=FONT)

    hs = hist_df.sort_values('Mes') if not hist_df.empty else hist_df
    if not hs.empty:
        n   = len(hs)
        x   = list(range(n))
        mn  = hs['Lance_Min'].tolist()
        mx  = hs['Lance_Max'].tolist()
        ct  = hs['QT_Contemp'].tolist()

        # Tamanho de marcador e espessura de linha adaptados à quantidade de pontos
        ms  = max(4, int(10 - n * 0.4))   # diminui marcador conforme mais meses
        lw  = max(1.2, 2.2 - n * 0.06)
        ann_fs = fs(max(5, 8 - n // 3))   # fonte da anotação diminui c/ mais pontos

        # ── Gráfico 1: Lance Min/Max ──────────────────────────────────────────
        ax1.fill_between(x, mn, mx, color=C['red_l'], alpha=0.7, zorder=1)
        ax1.plot(x, mx, color=acc_color, lw=lw, marker='o', markersize=ms,
                 zorder=3, markerfacecolor=C['bg3'],
                 markeredgewidth=lw * 0.7, markeredgecolor=acc_color)
        ax1.plot(x, mn, color=C['green'], lw=lw, marker='o', markersize=ms,
                 zorder=3, markerfacecolor=C['bg3'],
                 markeredgewidth=lw * 0.7, markeredgecolor=C['green'])

        # Anotações: só mostrar se não lotado demais
        if n <= 8:
            for i, (v_mn, v_mx) in enumerate(zip(mn, mx)):
                ax1.annotate(f'{v_mx:.1f}', (i, v_mx),
                             xytext=(0, ms + 3), textcoords='offset points',
                             ha='center', fontsize=ann_fs,
                             color=acc_color, fontweight='bold', fontfamily=FONT)
                ax1.annotate(f'{v_mn:.1f}', (i, v_mn),
                             xytext=(0, -(ms + 8)), textcoords='offset points',
                             ha='center', fontsize=ann_fs,
                             color=C['green'], fontweight='bold', fontfamily=FONT)
        elif n <= 12:
            # Só anota nos pontos ímpares para evitar sobreposição
            for i, (v_mn, v_mx) in enumerate(zip(mn, mx)):
                if i % 2 == n % 2:  # alterna
                    ax1.annotate(f'{v_mx:.1f}', (i, v_mx),
                                 xytext=(0, ms + 3), textcoords='offset points',
                                 ha='center', fontsize=ann_fs,
                                 color=acc_color, fontweight='bold', fontfamily=FONT)
                    ax1.annotate(f'{v_mn:.1f}', (i, v_mn),
                                 xytext=(0, -(ms + 7)), textcoords='offset points',
                                 ha='center', fontsize=ann_fs,
                                 color=C['green'], fontweight='bold', fontfamily=FONT)

        ax1.set_xticks(x)
        ax1.set_xticklabels(_fmt_m(hs['Mes']),
                            rotation=45, ha='right', fontsize=fs(7))

        # ── Gráfico 2: Contemplações ──────────────────────────────────────────
        ax2.fill_between(x, ct, color=C['green_l'], alpha=0.8, zorder=1)
        ax2.plot(x, ct, color=C['green'], lw=lw, marker='o', markersize=ms,
                 zorder=3, markerfacecolor=C['bg3'],
                 markeredgewidth=lw * 0.7, markeredgecolor=C['green'])

        if n <= 8:
            for i, v in enumerate(ct):
                ax2.annotate(f'{int(v)}', (i, v),
                             xytext=(0, ms + 3), textcoords='offset points',
                             ha='center', fontsize=ann_fs,
                             color=C['green'], fontweight='bold', fontfamily=FONT)
        elif n <= 12:
            for i, v in enumerate(ct):
                if i % 2 == n % 2:
                    ax2.annotate(f'{int(v)}', (i, v),
                                 xytext=(0, ms + 3), textcoords='offset points',
                                 ha='center', fontsize=ann_fs,
                                 color=C['green'], fontweight='bold', fontfamily=FONT)

        ax2.set_xticks(x)
        ax2.set_xticklabels(_fmt_m(hs['Mes']),
                            rotation=45, ha='right', fontsize=fs(7))
    else:
        for ax in (ax1, ax2):
            ax.text(0.5, 0.5, 'Sem histórico', ha='center', va='center',
                    transform=ax.transAxes, color=C['text3'],
                    fontsize=fs(10), fontfamily=FONT, style='italic')
    return fig

# ══════════════════════════════════════════════════════════════════════════════
# CARD – barra de info compacta no topo + gráfico dominando o espaço
# ══════════════════════════════════════════════════════════════════════════════
def make_card(parent, vaga_row, hist_df, acc_color, favorito=False,
              card_h=220, card_w=600, scale=1.0, disponivel=True):
    fs     = lambda b: max(8,  int(b * scale * 1.35))
    fs_tbl = lambda b: max(9,  int(b * scale * 1.45))

    bc   = C['gold']    if favorito else acc_color
    cbg  = '#141A2A'    if favorito else C['bg3']
    hbg  = '#1F1500'    if favorito else C['bg4']
    acc  = C['gold']    if favorito else acc_color
    grupo = str(vaga_row.get('Grupo', '?')).strip()

    outer = tk.Frame(parent, bg=bc, padx=2, pady=2)
    inner = tk.Frame(outer, bg=cbg)
    inner.pack(fill='both', expand=True)

    # ── BARRA DE TOPO: grupo + infos + tabela resumo ──────────────────────────
    hdr = tk.Frame(inner, bg=hbg)
    hdr.pack(fill='x')

    # Bloco GRUPO (lado esquerdo)
    gblk = tk.Frame(hdr, bg=acc, padx=int(10*scale), pady=int(4*scale))
    gblk.pack(side='left', fill='y')
    tk.Label(gblk, text="GRUPO",  font=(FONT, fs(6),  'bold'), bg=acc, fg=C['bg']).pack(anchor='w')
    tk.Label(gblk, text=grupo,    font=(FONT, fs(15), 'bold'), bg=acc, fg=C['bg']).pack(anchor='w')

    # Infos ou aviso de indisponível
    if disponivel:
        info_f = tk.Frame(hdr, bg=hbg, padx=int(8*scale), pady=int(3*scale))
        info_f.pack(side='left', fill='y')
        infos = [
            ("Credito",      f"{vaga_row['Crédito mínimo']} → {vaga_row['Crédito máximo']}"),
            ("Parcela",      str(vaga_row['Valor médio parcela'])),
            ("Prazo",        str(vaga_row['Meses restantes'])),
            ("Vagas livres", str(vaga_row['_vagas_livres'])),
        ]
        for col, (lbl, val) in enumerate(infos):
            f = tk.Frame(info_f, bg=hbg)
            f.grid(row=0, column=col, padx=int(fs(7)), sticky='w')
            tk.Label(f, text=lbl, font=(FONT, fs(6)),
                     bg=hbg, fg=C['text3']).pack(anchor='w')
            tk.Label(f, text=val, font=(FONT, fs(9), 'bold'),
                     bg=hbg, fg=C['text']).pack(anchor='w')
    else:
        info_f = tk.Frame(hdr, bg=hbg, padx=int(8*scale), pady=int(3*scale))
        info_f.pack(side='left', fill='y')
        tk.Label(info_f, text="Grupo indisponivel no momento",
                 font=(FONT, fs(8), 'italic'), bg=hbg, fg=C['orange']).pack(pady=4)

    # Tabela de médias (lado direito da barra)
    _summary_table(hdr, hist_df, hbg, acc, scale, fs_tbl)

    # ── GRÁFICO: ocupa todo o espaço restante do card ─────────────────────────
    # Desconta a altura da barra de topo (~40px) para calcular a altura do gráfico
    graf_h = max(120, card_h - int(44 * scale))
    cf = tk.Frame(inner, bg=cbg)
    cf.pack(fill='both', expand=True, padx=2, pady=2)

    fig = build_figure(hist_df, graf_h, card_w, acc_color, scale)
    fig.set_facecolor(cbg)
    canvas = FigureCanvasTkAgg(fig, master=cf)
    canvas.draw()
    w = canvas.get_tk_widget()
    w.pack(fill='both', expand=True)
    w.configure(bg=cbg, highlightthickness=0)
    return outer

def make_card_v3(parent, vaga_row, hist_df, acc_color, favorito=False,
                 card_h=220, card_w=600, scale=1.0, disponivel=True):
    fs = lambda b: max(8, int(b * scale * 1.35))
    fs_tbl = lambda b: max(9, int(b * scale * 1.35))

    bc = C['gold'] if favorito else acc_color
    cbg = '#141A2A' if favorito else C['bg3']
    hbg = '#1F1500' if favorito else C['bg4']
    acc = C['gold'] if favorito else acc_color
    grupo = str(vaga_row.get('Grupo', '?')).strip()

    def row_val(row, *keys, default='—'):
        for key in keys:
            if key in row and str(row[key]).strip() != '':
                return row[key]
        return default

    outer = tk.Frame(parent, bg=bc, padx=2, pady=2)
    inner = tk.Frame(outer, bg=cbg)
    inner.pack(fill='both', expand=True)

    hdr = tk.Frame(inner, bg=hbg)
    hdr.pack(fill='x')

    gblk = tk.Frame(hdr, bg=acc, padx=int(10 * scale), pady=int(4 * scale))
    gblk.pack(side='left', fill='y')
    tk.Label(gblk, text="GRUPO", font=(FONT, fs(6), 'bold'), bg=acc, fg=C['bg']).pack(anchor='w')
    tk.Label(gblk, text=grupo, font=(FONT, fs(15), 'bold'), bg=acc, fg=C['bg']).pack(anchor='w')

    if disponivel:
        info_f = tk.Frame(hdr, bg=hbg, padx=int(8 * scale), pady=int(3 * scale))
        info_f.pack(side='left', fill='y')
        infos = [
            ("Credito", f"{row_val(vaga_row, 'Crédito mínimo', 'CrÃ©dito mÃ­nimo', 'CrÃƒÂ©dito mÃƒÂ­nimo')} → {row_val(vaga_row, 'Crédito máximo', 'CrÃ©dito mÃ¡ximo', 'CrÃƒÂ©dito mÃƒÂ¡ximo')}"),
            ("Parcela", str(row_val(vaga_row, 'Valor médio parcela', 'Valor mÃ©dio parcela', 'Valor mÃƒÂ©dio parcela'))),
            ("Prazo", str(row_val(vaga_row, 'Meses restantes'))),
            ("Vagas livres", str(row_val(vaga_row, '_vagas_livres'))),
        ]
        for col, (lbl, val) in enumerate(infos):
            f = tk.Frame(info_f, bg=hbg)
            f.grid(row=0, column=col, padx=int(fs(6)), sticky='w')
            tk.Label(f, text=lbl, font=(FONT, fs(6)), bg=hbg, fg=C['text3']).pack(anchor='w')
            tk.Label(f, text=val, font=(FONT, fs(8), 'bold'), bg=hbg, fg=C['text']).pack(anchor='w')
    else:
        info_f = tk.Frame(hdr, bg=hbg, padx=int(8 * scale), pady=int(3 * scale))
        info_f.pack(side='left', fill='y')
        tk.Label(info_f, text="Grupo indisponivel no momento",
                 font=(FONT, fs(8), 'italic'), bg=hbg, fg=C['orange']).pack(pady=4)

    _history_highlights_v2(inner, hist_df, cbg, acc, scale)

    graf_h = max(210, card_h - int(72 * scale))
    cf = tk.Frame(inner, bg=cbg)
    cf.pack(fill='both', expand=True, padx=2, pady=2)

    fig = build_figure(hist_df, graf_h, card_w, acc_color, scale)
    fig.set_facecolor(cbg)
    canvas = FigureCanvasTkAgg(fig, master=cf)
    canvas.draw()
    w = canvas.get_tk_widget()
    w.pack(fill='both', expand=True)
    w.configure(bg=cbg, highlightthickness=0)
    return outer

def _summary_table(parent, hist_df, bg, acc, scale=1.0, fs_tbl=None):
    if fs_tbl is None:
        fs_tbl = lambda b: max(9, int(b * scale * 1.45))
    fs = fs_tbl
    padx = int(11 * scale)
    pady = int(5 * scale)
    frm = tk.Frame(parent, bg=bg, padx=int(12*scale), pady=int(6*scale))
    frm.pack(side='right')
    for c, h in enumerate(['Período', 'Média %', 'Contemp.']):
        tk.Label(frm, text=h, font=(FONT, fs(8), 'bold'),
                 bg=C['tbl_h'], fg=acc,
                 padx=padx, pady=pady
                 ).grid(row=0, column=c, sticky='nsew', padx=1, pady=1)
    for r, n in enumerate([12, 6, 3], 1):
        tail = hist_df.sort_values('Mes').tail(n) if not hist_df.empty else pd.DataFrame()
        if tail.empty:
            med, cmp = '—', '—'
        else:
            med = f"{((tail['Lance_Min'].mean()+tail['Lance_Max'].mean())/2):.2f}%"
            cmp = str(int(tail['QT_Contemp'].sum()))
        rbg = C['bg3'] if r % 2 else C['tbl_alt']
        fg_med = acc        if med != '—' else C['text3']
        fg_cmp = C['green'] if cmp != '—' else C['text3']
        for c,(val,fg) in enumerate([(f'{n}m', C['text2']), (med, fg_med), (cmp, fg_cmp)]):
            tk.Label(frm, text=val, font=(FONT, fs(9), 'bold' if c>0 else 'normal'),
                     bg=rbg, fg=fg,
                     padx=padx, pady=pady, anchor='center'
                     ).grid(row=r, column=c, sticky='nsew', padx=1)

def _calc_history_metrics_v2(hist_df):
    if hist_df is None or hist_df.empty:
        return None
    hs = hist_df.sort_values('Mes').copy()
    last = hs.iloc[-1]
    tail_3 = hs.tail(3)
    media = (float(last['Lance_Min']) + float(last['Lance_Max'])) / 2
    media_3m = (tail_3['Lance_Min'].mean() + tail_3['Lance_Max'].mean()) / 2
    return {
        'periodo': _fmt_m([last['Mes']])[0],
        'min': float(last['Lance_Min']),
        'max': float(last['Lance_Max']),
        'media': media,
        'media_3m': media_3m,
        'cont': int(last['QT_Contemp']),
    }

def _history_highlights_v2(parent, hist_df, bg, acc, scale=1.0):
    fs = lambda b: max(7, int(b * scale * 1.18))
    metrics = _calc_history_metrics_v2(hist_df)

    band = tk.Frame(parent, bg=bg, padx=int(6 * scale), pady=int(3 * scale))
    band.pack(fill='x')

    head = tk.Frame(band, bg=bg)
    head.pack(fill='x', pady=(0, 2))
    tk.Label(head, text='Historico de lances em destaque',
             font=(FONT, fs(7), 'bold'), bg=bg, fg=C['white']).pack(side='left')
    tk.Label(head, text=f"Base: {metrics['periodo']}" if metrics else 'Sem dados historicos',
             font=(FONT, fs(6)), bg=bg, fg=C['text2']).pack(side='right')

    row = tk.Frame(band, bg=bg)
    row.pack(fill='x')

    def box(parent_box, titulo, valor, detalhe, fg, box_bg):
        frm = tk.Frame(parent_box, bg=box_bg, padx=int(7 * scale), pady=int(5 * scale),
                       highlightbackground=C['border'], highlightthickness=1)
        frm.pack(side='left', fill='both', expand=True, padx=1)
        tk.Label(frm, text=titulo, font=(FONT, fs(6), 'bold'),
                 bg=box_bg, fg=C['text2']).pack(anchor='w')
        tk.Label(frm, text=valor, font=(FONT, fs(9), 'bold'),
                 bg=box_bg, fg=fg).pack(anchor='w', pady=(0, 0))
        tk.Label(frm, text=detalhe, font=(FONT, fs(6)),
                 bg=box_bg, fg=C['text']).pack(anchor='w', pady=(1, 0))

    if not metrics:
        box(row, 'Historico', 'Sem dados', 'Configure o arquivo de historico para exibir os lances mensais.', C['text3'], C['bg4'])
        return

    delta_media = metrics['media'] - metrics['media_3m']
    delta_txt = f"{'Acima' if delta_media > 0 else 'Abaixo'} {abs(delta_media):.2f}% vs 3m" if abs(delta_media) >= 0.05 else 'Estavel vs 3m'

    box(row, 'Lance medio', f"{metrics['media']:.2f}%", delta_txt, acc, C['bg4'])
    box(row, 'Faixa do mes', f"{metrics['min']:.1f}% a {metrics['max']:.1f}%", 'Min e max do ultimo fechamento.', C['white'], C['navy'])
    box(row, 'Contemplacoes', str(metrics['cont']), f"Media 3m: {metrics['media_3m']:.2f}%", acc, C['bg4'])

def build_figure(hist_df, card_h_px, card_w_px, acc_color, scale):
    """
    Historico com foco em legibilidade quando houver 3 grupos em tela.
    O painel de lances recebe mais area e todos os meses ficam rotulados.
    """
    n_meses = 12
    hist_df = hist_df.sort_values('Mes').tail(n_meses) if not hist_df.empty else hist_df.copy()

    dpi = 96
    fig_h = max(1.75, (card_h_px - int(38 * scale)) / dpi)
    fig_w = max(4.2, card_w_px / dpi)
    fs = lambda b: max(8, int(b * scale * 1.30))

    fig = plt.Figure(figsize=(fig_w, fig_h), facecolor=C['bg3'], dpi=dpi)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.85, 1.0])
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    fig.subplots_adjust(left=0.06, right=0.985, top=0.82, bottom=0.24, wspace=0.12)

    for ax in (ax1, ax2):
        ax.set_facecolor(C['plot_bg'])
        for sp in ax.spines.values():
            sp.set_edgecolor(C['border'])
            sp.set_linewidth(0.8)
        ax.grid(axis='y', color=C['plot_grid'], linewidth=0.7, linestyle='--', alpha=0.9, zorder=0)
        ax.tick_params(axis='x', colors=C['text2'], labelsize=fs(7), length=0, pad=5)
        ax.tick_params(axis='y', colors=C['text2'], labelsize=fs(7), length=0, pad=4)

    fig.text(0.275, 0.92, 'Historico de Lances (%)',
             ha='center', va='center', color=C['white'],
             fontsize=fs(10), fontweight='bold', fontfamily=FONT)
    fig.text(0.79, 0.92, 'Contemplacoes',
             ha='center', va='center', color=C['white'],
             fontsize=fs(9), fontweight='bold', fontfamily=FONT)

    hs = hist_df.sort_values('Mes') if not hist_df.empty else hist_df
    if hs.empty:
        for ax in (ax1, ax2):
            ax.text(0.5, 0.5, 'Sem historico', ha='center', va='center',
                    transform=ax.transAxes, color=C['text3'],
                    fontsize=fs(10), fontfamily=FONT, style='italic')
            ax.set_xticks([])
            ax.set_yticks([])
        return fig

    x = list(range(len(hs)))
    meses = _fmt_m(hs['Mes'])
    mn = hs['Lance_Min'].astype(float).tolist()
    mx = hs['Lance_Max'].astype(float).tolist()
    ct = hs['QT_Contemp'].astype(float).tolist()
    ms = max(4, int(8 - len(hs) * 0.2))
    lw = max(1.8, 2.8 - len(hs) * 0.05)
    ann_fs = max(7, fs(6))

    cor_min = C['white']
    cor_max = acc_color

    ax1.fill_between(x, mn, mx, color=acc_color, alpha=0.15, zorder=1)
    ax1.plot(x, mx, color=cor_max, lw=lw, marker='o', markersize=ms,
             zorder=3, markerfacecolor=C['bg3'],
             markeredgewidth=1.1, markeredgecolor=cor_max)
    ax1.plot(x, mn, color=cor_min, lw=lw * 0.95, marker='o', markersize=ms,
             zorder=3, markerfacecolor=C['bg3'],
             markeredgewidth=1.1, markeredgecolor=cor_min)

    for i, (vmin, vmax) in enumerate(zip(mn, mx)):
        ax1.annotate(f'{vmax:.1f}', (i, vmax),
                     xytext=(0, 8), textcoords='offset points',
                     ha='center', fontsize=ann_fs, color=cor_max,
                     fontweight='bold', fontfamily=FONT,
                     bbox=dict(boxstyle='round,pad=0.12', facecolor=C['bg3'], edgecolor='none', alpha=0.82))
        ax1.annotate(f'{vmin:.1f}', (i, vmin),
                     xytext=(0, -14), textcoords='offset points',
                     ha='center', fontsize=ann_fs, color=cor_min,
                     fontweight='bold', fontfamily=FONT,
                     bbox=dict(boxstyle='round,pad=0.12', facecolor=C['bg3'], edgecolor='none', alpha=0.82))

    ax1.set_xticks(x)
    ax1.set_xticklabels(meses, rotation=0, ha='center', fontsize=fs(7), fontfamily=FONT)
    ax1.set_ylim(min(mn) - 1.6, max(mx) + 1.9)
    ax1.set_ylabel('%', color=C['text2'], fontsize=fs(7), fontfamily=FONT, labelpad=4)

    ax2.bar(x, ct, color=acc_color, alpha=0.88, width=0.62, zorder=2)
    ax2.plot(x, ct, color=C['white'], lw=1.1, alpha=0.55, zorder=3)
    for i, v in enumerate(ct):
        ax2.annotate(f'{int(v)}', (i, v),
                     xytext=(0, 6), textcoords='offset points',
                     ha='center', fontsize=ann_fs, color=C['white'],
                     fontweight='bold', fontfamily=FONT)
    ax2.set_xticks(x)
    ax2.set_xticklabels(meses, rotation=0, ha='center', fontsize=fs(7), fontfamily=FONT)
    ax2.set_ylim(0, max(ct) * 1.28 if max(ct) > 0 else 1)
    return fig

def make_card(parent, vaga_row, hist_df, acc_color, favorito=False,
              card_h=220, card_w=600, scale=1.0, disponivel=True):
    fs = lambda b: max(8, int(b * scale * 1.35))
    fs_tbl = lambda b: max(9, int(b * scale * 1.35))

    bc = C['gold'] if favorito else acc_color
    cbg = '#141A2A' if favorito else C['bg3']
    hbg = '#1F1500' if favorito else C['bg4']
    acc = C['gold'] if favorito else acc_color
    grupo = str(vaga_row.get('Grupo', '?')).strip()

    outer = tk.Frame(parent, bg=bc, padx=2, pady=2)
    inner = tk.Frame(outer, bg=cbg)
    inner.pack(fill='both', expand=True)

    hdr = tk.Frame(inner, bg=hbg)
    hdr.pack(fill='x')

    gblk = tk.Frame(hdr, bg=acc, padx=int(10 * scale), pady=int(4 * scale))
    gblk.pack(side='left', fill='y')
    tk.Label(gblk, text="GRUPO", font=(FONT, fs(6), 'bold'), bg=acc, fg=C['bg']).pack(anchor='w')
    tk.Label(gblk, text=grupo, font=(FONT, fs(15), 'bold'), bg=acc, fg=C['bg']).pack(anchor='w')

    if disponivel:
        info_f = tk.Frame(hdr, bg=hbg, padx=int(8 * scale), pady=int(3 * scale))
        info_f.pack(side='left', fill='y')
        infos = [
            ("Credito", f"{vaga_row['CrÃ©dito mÃ­nimo']} â†’ {vaga_row['CrÃ©dito mÃ¡ximo']}"),
            ("Parcela", str(vaga_row['Valor mÃ©dio parcela'])),
            ("Prazo", str(vaga_row['Meses restantes'])),
            ("Vagas livres", str(vaga_row['_vagas_livres'])),
        ]
        for col, (lbl, val) in enumerate(infos):
            f = tk.Frame(info_f, bg=hbg)
            f.grid(row=0, column=col, padx=int(fs(6)), sticky='w')
            tk.Label(f, text=lbl, font=(FONT, fs(6)), bg=hbg, fg=C['text3']).pack(anchor='w')
            tk.Label(f, text=val, font=(FONT, fs(8), 'bold'), bg=hbg, fg=C['text']).pack(anchor='w')
    else:
        info_f = tk.Frame(hdr, bg=hbg, padx=int(8 * scale), pady=int(3 * scale))
        info_f.pack(side='left', fill='y')
        tk.Label(info_f, text="Grupo indisponivel no momento",
                 font=(FONT, fs(8), 'italic'), bg=hbg, fg=C['orange']).pack(pady=4)

    _summary_table(hdr, hist_df, hbg, acc, scale, fs_tbl)
    _history_highlights_v2(inner, hist_df, cbg, acc, scale)

    graf_h = max(160, card_h - int(122 * scale))
    cf = tk.Frame(inner, bg=cbg)
    cf.pack(fill='both', expand=True, padx=2, pady=2)

    fig = build_figure(hist_df, graf_h, card_w, acc_color, scale)
    fig.set_facecolor(cbg)
    canvas = FigureCanvasTkAgg(fig, master=cf)
    canvas.draw()
    w = canvas.get_tk_widget()
    w.pack(fill='both', expand=True)
    w.configure(bg=cbg, highlightthickness=0)
    return outer

# ══════════════════════════════════════════════════════════════════════════════
# COLUNA DE CATEGORIA – com cards de tamanhos iguais usando grid
# ══════════════════════════════════════════════════════════════════════════════
class CatColumn(tk.Frame):
    def __init__(self, parent, cat, df_hist_ref, scale_ref, **kw):
        super().__init__(parent, bg=C['bg'], **kw)
        self.cat         = cat
        self.df_hist_ref = df_hist_ref
        self.scale_ref   = scale_ref
        self.df_vagas    = None
        self.grupos_rot  = []
        self.rot_index   = 0
        self._rot_job    = None
        icon, label, acc = LABELS[cat]
        self.acc = acc

        sub = tk.Frame(self, bg=C['bg4'])
        sub.pack(fill='x')
        tk.Frame(sub, bg=acc, height=3).pack(fill='x')
        inner_hdr = tk.Frame(sub, bg=C['bg4'], pady=5)
        inner_hdr.pack(fill='x')
        tk.Label(inner_hdr, text=f"{icon}  {label}",
                 font=(FONT, 12, 'bold'), bg=C['bg4'], fg=acc).pack(side='left', padx=10)
        self.lbl_prog = tk.Label(inner_hdr, text="", font=(FONT, 8),
                                 bg=C['bg4'], fg=C['text3'])
        self.lbl_prog.pack(side='right', padx=8)

        self.cards_container = tk.Frame(self, bg=C['bg'])
        self.cards_container.pack(fill='both', expand=True, pady=(5, 0))

    def load(self):
        path = CONFIG[self.cat].get('arquivo', '')
        if path and os.path.exists(path):
            self.df_vagas = load_vagas(path, self.cat)
        else:
            self.df_vagas = None

    def get_hist(self, grupo):
        df = self.df_hist_ref()
        if df is None or df.empty: return pd.DataFrame()
        return df[df['CD_Grupo'] == str(grupo).strip().upper()].copy()

    def _calculate_card_dimensions(self, n_cards):
        self.cards_container.update_idletasks()
        h = self.cards_container.winfo_height()
        w = self.cards_container.winfo_width()
        if h <= 1:
            h = self.winfo_screenheight() - 200
        if w <= 1:
            w = self.winfo_screenwidth() // 3 - 20
        spacing = (n_cards - 1) * 4
        card_h = max(180, (h - spacing) // n_cards)
        card_w = max(270, w - 8)
        return card_h, card_w

    def _clear_cards(self):
        for widget in self.cards_container.winfo_children():
            widget.destroy()

    def _add_card(self, row, vaga_row, hist_df, favorito, card_h, card_w, disponivel):
        cell = tk.Frame(self.cards_container, bg=C['bg'])
        cell.grid(row=row, column=0, sticky='nsew', pady=2)
        card = make_card_v3(cell, vaga_row, hist_df, self.acc, favorito=favorito,
                         card_h=card_h, card_w=card_w, scale=self.scale_ref(),
                         disponivel=disponivel)
        card.pack(fill='both', expand=True)

    def render_cards(self):
        self._clear_cards()
        favs = CONFIG[self.cat].get('favoritos', [])
        n_rot = CONFIG[self.cat].get('vagas_simultaneas', 2)
        n_fav = 1 if favs else 0
        total_cards = n_fav + n_rot

        for i in range(total_cards):
            self.cards_container.grid_rowconfigure(i, weight=1)
        self.cards_container.grid_columnconfigure(0, weight=1)

        card_h, card_w = self._calculate_card_dimensions(total_cards)

        if favs:
            g = favs[0]
            row_data = None
            disponivel = False
            if self.df_vagas is not None:
                match = self.df_vagas[self.df_vagas['Grupo'] == g]
                if not match.empty:
                    row_data = match.iloc[0]
                    disponivel = True
            if not disponivel:
                row_data = {'Grupo': g}
            self._add_card(0, row_data, self.get_hist(g), True, card_h, card_w, disponivel)

        if self.grupos_rot and self.df_vagas is not None:
            df_filt = filtrar_vagas(self.df_vagas, self.cat)
            start_idx = self.rot_index
            for i in range(n_rot):
                idx = (start_idx + i) % len(self.grupos_rot)
                grupo = self.grupos_rot[idx]
                rows = df_filt[df_filt['Grupo'] == grupo]
                if not rows.empty:
                    row_data = rows.iloc[0]
                    self._add_card(n_fav + i, row_data, self.get_hist(grupo), False, card_h, card_w, True)
                else:
                    self._add_card(n_fav + i, {'Grupo': grupo}, self.get_hist(grupo), False, card_h, card_w, False)
        else:
            for i in range(n_rot):
                self._add_card(n_fav + i, {'Grupo': '---'}, pd.DataFrame(), False, card_h, card_w, False)

        if self.grupos_rot:
            n_show = n_rot
            total = len(self.grupos_rot)
            s = (self.rot_index % total) + 1
            e = min(s + n_show - 1, total)
            shown = [self.grupos_rot[(self.rot_index + i) % total] for i in range(n_show)]
            self.lbl_prog.config(text=f"{s}–{e} / {total}  ({' · '.join(shown)})")
        else:
            self.lbl_prog.config(text="")

    def schedule_rot(self):
        self.render_cards()
        self.rot_index += CONFIG[self.cat].get('vagas_simultaneas', 2)
        if self._rot_job:
            self.after_cancel(self._rot_job)
        iv = CONFIG[self.cat].get('rotacao_intervalo', 12) * 1000
        self._rot_job = self.after(iv, self.schedule_rot)

    def refresh(self):
        self.load()
        if self.df_vagas is not None:
            df_filt = filtrar_vagas(self.df_vagas, self.cat)
            favs = set(CONFIG[self.cat].get('favoritos', []))
            self.grupos_rot = [g for g in df_filt['Grupo'].tolist() if g not in favs]
        else:
            self.grupos_rot = []
        self.rot_index = 0
        self.schedule_rot()

# ══════════════════════════════════════════════════════════════════════════════
# 🖥️ FUNÇÕES PARA DETECÇÃO DE MONITORES (Windows)
# ══════════════════════════════════════════════════════════════════════════════
def get_monitors_windows():
    return [] # Desativado no macOS

# O código original de detecção do Windows foi comentado para evitar erros no Mac
"""
def get_monitors_windows_original():
    monitors = []
    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32),
        ]
    def monitor_enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
        mi = MONITORINFOEXW()
        mi.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if ctypes.windll.user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi)):
            monitors.append({
                'x': mi.rcMonitor.left,
                'y': mi.rcMonitor.top,
                'width': mi.rcMonitor.right - mi.rcMonitor.left,
                'height': mi.rcMonitor.bottom - mi.rcMonitor.top,
                'device': mi.szDevice,
            })
        return True
    MonitorEnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    callback = MonitorEnumProc(monitor_enum_proc)
    ctypes.windll.user32.EnumDisplayMonitors(None, None, callback, 0)
    return monitors
"""

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD PRINCIPAL – com seleção de monitor e botão vermelho SAIR (CORRIGIDO)
# ══════════════════════════════════════════════════════════════════════════════
class DashboardTV(tk.Toplevel):
    def __init__(self, master=None, keep_on_top=True, exit_on_close=False):
        super().__init__(master)
        self.keep_on_top = keep_on_top
        self.exit_on_close = exit_on_close
        self.title("Master Prime – Dashboard de Vagas")
        self.configure(bg=C['bg'])
        
        # Flag para evitar múltiplas aplicações simultâneas
        self._moving_monitor = False
        
        # Aplica configuração de monitor ANTES de ativar fullscreen
        self._apply_monitor_settings(init=True)
        
        # Agora ativa fullscreen
        self.attributes('-fullscreen', CONFIG.get('fullscreen', True))
        self.resizable(False, False)
        self.protocol('WM_DELETE_WINDOW', self._sair)
        self.bind('<Escape>',     lambda e: None)
        self.bind('<F11>',        lambda e: self.attributes('-fullscreen', True))
        self.bind('<Unmap>',      self._prevent_minimize)
        self.bind('<Control-p>',  lambda e: self._open_control())
        self.bind('<Control-q>',  lambda e: self._sair())

        self.df_hist    = pd.DataFrame()
        self._rel_job   = None
        self._rt_job    = None
        self._tv_guard_job = None
        self.control_win = None
        self._file_mtimes = {}
        self._last_monitor_signature = None

        self._build_ui()
        self._reload_all()
        self._schedule_reload()
        self._poll_dirty()
        self._start_real_time()
        self.after(250, self._enforce_fullscreen)
        self.after(1200, self._tv_guard_loop)
        if self.keep_on_top:
            self._keep_on_top()   # garante que o dashboard fique sempre acima

    def _apply_monitor_settings(self, init=False):
        """Move a janela para o monitor selecionado sem flickar."""
        if self._moving_monitor and not init:
            return
        self._moving_monitor = True

        monitors = get_monitors_windows()
        if not monitors:
            self._moving_monitor = False
            return

        idx = CONFIG.get('monitor_index', 0)
        if idx >= len(monitors):
            idx = 0

        mon = monitors[idx]
        target_x = mon['x']
        target_y = mon['y']
        w = mon['width']
        h = mon['height']

        def _do_move():
            # 1. Sai do fullscreen
            self.attributes('-fullscreen', False)
            self.update_idletasks()
            # 2. Posiciona no monitor alvo
            self.geometry(f"{w}x{h}+{target_x}+{target_y}")
            self.update_idletasks()
            # 3. Re-ativa fullscreen após a janela ter se movido (150ms é suficiente)
            self.after(150, _reactivate)

        def _reactivate():
            self.attributes('-fullscreen', True)
            self.update_idletasks()
            self._moving_monitor = False

        if init:
            # No init ainda nao ha event loop rodando; faz direto
            self.attributes('-fullscreen', False)
            self.geometry(f"{w}x{h}+{target_x}+{target_y}")
            self.update_idletasks()
            self._moving_monitor = False
        else:
            _do_move()

    def _sair(self):
        if self.control_win and self.control_win.winfo_exists():
            self.control_win.destroy()
        if self._rel_job:
            self.after_cancel(self._rel_job)
        if self._rt_job:
            self.after_cancel(self._rt_job)
        if self._tv_guard_job:
            self.after_cancel(self._tv_guard_job)
        self.destroy()
        if self.exit_on_close and self.master:
            try:
                self.master.destroy()
            except Exception:
                pass

    def _enforce_fullscreen(self):
        try:
            if self.winfo_exists():
                self.attributes('-fullscreen', True)
                self.attributes('-topmost', bool(self.keep_on_top))
                self.update_idletasks()
        except Exception:
            pass

    def _prevent_minimize(self, _):
        self.after(10, self.deiconify)
        self.after(30, self._enforce_fullscreen)

    def _tv_guard_loop(self):
        try:
            if not self.winfo_exists():
                return
            monitors = get_monitors_windows()
            signature = tuple((m['device'], m['x'], m['y'], m['width'], m['height']) for m in monitors)
            if signature != self._last_monitor_signature:
                self._last_monitor_signature = signature
                self._apply_monitor_settings()
            if not bool(self.attributes('-fullscreen')):
                self._enforce_fullscreen()
        except Exception:
            pass
        self._tv_guard_job = self.after(2500, self._tv_guard_loop)

    def _keep_on_top(self):
        """Recoloca o dashboard no topo a cada 3s, evitando que janelas externas o sobreponham."""
        try:
            if self.winfo_exists():
                # Não interfere quando o painel de controle está aberto e em foco
                ctrl_open = (self.control_win and self.control_win.winfo_exists())
                if not ctrl_open:
                    self.attributes('-topmost', True)
                    self.lift()
        except Exception:
            pass
        if self.keep_on_top:
            self.after(3000, self._keep_on_top)

    def _build_ui(self):
        tk.Frame(self, bg=C['orange'], height=3).pack(fill='x')
        hdr = tk.Frame(self, bg=C['navy'])
        hdr.pack(fill='x')
        logo = tk.Frame(hdr, bg=C['orange'], padx=14, pady=0)
        logo.pack(side='left', fill='y')
        tk.Label(logo, text="M", font=(FONT, 26, 'bold'), bg=C['orange'], fg=C['white']).pack(pady=6)
        title_f = tk.Frame(hdr, bg=C['navy'], padx=14, pady=8)
        title_f.pack(side='left')
        tk.Label(title_f, text="MASTER PRIME CONSÓRCIOS",
                 font=(FONT, 17, 'bold'), bg=C['navy'], fg=C['white']).pack(anchor='w')
        tk.Label(title_f, text="Criado e gerenciado por Allan, Carlos, Erik, Larissa e Leonardo",
                 font=(FONT, 15, 'bold'), bg=C['navy'], fg=C['white']).pack(anchor='w')
        tk.Label(title_f, text="Painel de Vagas Disponíveis  ·  Automóveis · Imóveis · Veículos Pesados",
                 font=(FONT, 8), bg=C['navy'], fg=C['text2']).pack(anchor='w')
        right_f = tk.Frame(hdr, bg=C['navy'], padx=16)
        right_f.pack(side='right', fill='y')
        self.lbl_hora = tk.Label(right_f, font=(FONT, 20, 'bold'), bg=C['navy'], fg=C['white'])
        self.lbl_hora.pack(anchor='e', pady=(8,0))
        self.lbl_data = tk.Label(right_f, font=(FONT, 8), bg=C['navy'], fg=C['text2'])
        self.lbl_data.pack(anchor='e')
        btn_frame = tk.Frame(right_f, bg=C['navy'])
        btn_frame.pack(anchor='e', pady=(4,8))
        tk.Button(btn_frame, text='⚙  Painel', font=(FONT, 8, 'bold'),
                  bg=C['blue'], fg=C['white'], relief='flat', padx=10, pady=4,
                  cursor='hand2', command=self._open_control).pack(side='left', padx=(0,6))
        tk.Button(btn_frame, text='⛌  SAIR', font=(FONT, 8, 'bold'),
                  bg='#8B0000', fg=C['white'], relief='raised', padx=12, pady=4,
                  cursor='hand2', command=self._sair).pack(side='left')
        self._tick()
        tk.Frame(self, bg=C['orange'], height=3).pack(fill='x')
        body = tk.Frame(self, bg=C['bg'])
        body.pack(fill='both', expand=True)
        body.grid_columnconfigure(0, weight=1, uniform='col')
        body.grid_columnconfigure(1, weight=1, uniform='col')
        body.grid_columnconfigure(2, weight=1, uniform='col')
        body.grid_rowconfigure(0, weight=1)
        self.cols = {}
        for i, cat in enumerate(['auto', 'imovel', 'pesado']):
            col = CatColumn(body, cat,
                            df_hist_ref=lambda: self.df_hist,
                            scale_ref=lambda: CONFIG.get('ui_scale', 1.0) * CONFIG.get('font_scale', 1.0))
            col.grid(row=0, column=i, sticky='nsew',
                     padx=(10 if i==0 else 5, 5 if i<2 else 10), pady=8)
            if i < 2:
                tk.Frame(body, bg=C['border'], width=1).grid(row=0, column=i, sticky='nse', pady=8)
            self.cols[cat] = col
        self.status_var = tk.StringVar(value="Carregando...")
        sf = tk.Frame(self, bg=C['navy'])
        sf.pack(fill='x', side='bottom')
        tk.Label(sf, textvariable=self.status_var, font=(FONT, 7),
                 bg=C['navy'], fg=C['text2'], anchor='w', padx=12, pady=3).pack(side='left')

    def _tick(self):
        now = datetime.now()
        self.lbl_hora.config(text=now.strftime('%H:%M:%S'))
        dias  = {'Monday':'Seg','Tuesday':'Ter','Wednesday':'Qua',
                 'Thursday':'Qui','Friday':'Sex','Saturday':'Sáb','Sunday':'Dom'}
        meses = {'January':'Jan','February':'Fev','March':'Mar','April':'Abr',
                 'May':'Mai','June':'Jun','July':'Jul','August':'Ago',
                 'September':'Set','October':'Out','November':'Nov','December':'Dez'}
        s = now.strftime('%A, %d de %B de %Y')
        for en,pt in {**dias,**meses}.items(): s = s.replace(en,pt)
        self.lbl_data.config(text=s)
        self.after(1000, self._tick)

    def _get_file_mtime(self, path):
        try:
            return os.path.getmtime(path) if path and os.path.exists(path) else None
        except:
            return None

    def _check_files_changed(self):
        changed = False
        hist_path = CONFIG.get('historico', '')
        mtime = self._get_file_mtime(hist_path)
        if mtime is not None and self._file_mtimes.get('historico') != mtime:
            self._file_mtimes['historico'] = mtime
            changed = True
        for cat in ['auto', 'imovel', 'pesado']:
            path = CONFIG[cat].get('arquivo', '')
            mtime = self._get_file_mtime(path)
            key = f'vagas_{cat}'
            if mtime is not None and self._file_mtimes.get(key) != mtime:
                self._file_mtimes[key] = mtime
                changed = True
        return changed

    def _real_time_poll(self):
        if CONFIG.get('real_time', False):
            if self._check_files_changed():
                self._reload_all()
        self._rt_job = self.after(2000, self._real_time_poll)

    def _start_real_time(self):
        if self._rt_job:
            self.after_cancel(self._rt_job)
        if CONFIG.get('real_time', False):
            hist_path = CONFIG.get('historico', '')
            self._file_mtimes['historico'] = self._get_file_mtime(hist_path)
            for cat in ['auto', 'imovel', 'pesado']:
                path = CONFIG[cat].get('arquivo', '')
                self._file_mtimes[f'vagas_{cat}'] = self._get_file_mtime(path)
            self._real_time_poll()

    def _reload_all(self):
        try:
            path_h = CONFIG.get('historico','')
            if path_h and os.path.exists(path_h):
                self.df_hist = load_historico(path_h)
            else:
                self.df_hist = pd.DataFrame()
            for col in self.cols.values():
                col.refresh()
            gh = self.df_hist['CD_Grupo'].nunique() if not self.df_hist.empty else 0
            rt_status = " (tempo real)" if CONFIG.get('real_time') else ""
            self.status_var.set(
                f"✔ Atualizado {datetime.now().strftime('%H:%M:%S')}{rt_status}  |  "
                f"Histórico: {gh} grupos  |  Ctrl+P = Painel de controle"
            )
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            traceback.print_exc()

    def _schedule_reload(self):
        if self._rel_job: self.after_cancel(self._rel_job)
        iv = CONFIG.get('reload_intervalo', 300) * 1000
        self._rel_job = self.after(iv, self._do_reload)

    def _do_reload(self):
        self._reload_all()
        self._schedule_reload()

    def _poll_dirty(self):
        if CONFIG.get('_dirty'):
            CONFIG['_dirty'] = False
            if CONFIG.get('_reload_now'):
                CONFIG['_reload_now'] = False
                self._reload_all()
            else:
                for col in self.cols.values():
                    col.refresh()
            self._schedule_reload()
            self._start_real_time()
        self.after(500, self._poll_dirty)

    def _open_control(self):
        if self.control_win and self.control_win.winfo_exists():
            self.control_win.lift(); return
        self.control_win = ControlPanel(self)

# ══════════════════════════════════════════════════════════════════════════════
# PAINEL DE CONTROLE – com seletor de monitor corrigido
# ══════════════════════════════════════════════════════════════════════════════
class ControlPanel(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("⚙  Painel de Controle – Master Prime")
        self.configure(bg=C['bg2'])
        self.geometry('780x940')
        self.resizable(True, True)
        self.attributes('-topmost', True)
        self.protocol('WM_DELETE_WINDOW', self.destroy)

        style = ttk.Style(self)
        style.theme_use('default')
        style.configure('Dark.TNotebook',          background=C['bg2'], borderwidth=0)
        style.configure('Dark.TNotebook.Tab',      background=C['bg4'], foreground=C['text2'],
                         padding=[14,6], font=(FONT,9))
        style.map('Dark.TNotebook.Tab',
                  background=[('selected', C['blue'])],
                  foreground=[('selected', C['white'])])

        nb = ttk.Notebook(self, style='Dark.TNotebook')
        nb.pack(fill='both', expand=True, padx=0, pady=0)

        tab_geral  = self._scrollable(nb)
        nb.add(tab_geral,  text='⚙  Geral')
        self._build_tab_geral(tab_geral)

        self.cat_tabs = {}
        for cat in ['auto', 'imovel', 'pesado']:
            icon, label, acc = LABELS[cat]
            tab = self._scrollable(nb)
            nb.add(tab, text=f'{icon}  {label}')
            self._build_tab_cat(tab, cat, acc)
            self.cat_tabs[cat] = tab

        footer = tk.Frame(self, bg=C['bg2'])
        footer.pack(fill='x', padx=16, pady=10)

        def btn(t, bg, cmd):
            return tk.Button(footer, text=t, font=(FONT,9,'bold'), bg=bg, fg=C['white'],
                             relief='flat', padx=14, pady=7, cursor='hand2', command=cmd)

        btn("✅  Aplicar",         C['navy'],   self._apply       ).pack(side='left', padx=(0,6))
        btn("🔃  Recarregar xlsx", C['green'],  self._apply_reload).pack(side='left', padx=4)
        btn("💾  Salvar config",   C['orange'], self._save        ).pack(side='left', padx=4)
        btn("✖  Fechar",           '#555',      self.destroy      ).pack(side='left', padx=4)
        btn("⛌  Encerrar Dashboard", '#8B0000', self._encerrar_dashboard).pack(side='right')

        self.lbl_ok = tk.Label(self, text="", font=(FONT,8), bg=C['bg2'], fg=C['green'])
        self.lbl_ok.pack(pady=(0,6))

    def _encerrar_dashboard(self):
        if messagebox.askyesno("Encerrar", "Tem certeza que deseja fechar o Dashboard Master Prime?"):
            self.master._sair()

    def _scrollable(self, parent):
        outer = tk.Frame(parent, bg=C['bg2'])
        canvas= tk.Canvas(outer, bg=C['bg2'], highlightthickness=0)
        sb    = tk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        frm = tk.Frame(canvas, bg=C['bg2'])
        wid = canvas.create_window((0,0), window=frm, anchor='nw')
        frm.bind('<Configure>', lambda e: (
            canvas.configure(scrollregion=canvas.bbox('all')),
            canvas.itemconfig(wid, width=canvas.winfo_width())
        ))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(wid, width=e.width))
        canvas.bind_all('<MouseWheel>', lambda e: canvas.yview_scroll(int(-e.delta/120), 'units'))
        outer._inner = frm
        return outer

    def _sec(self, parent, txt, acc=C['blue_l']):
        frm = parent._inner if hasattr(parent,'_inner') else parent
        tk.Frame(frm, bg=C['border'], height=1).pack(fill='x', pady=(14,0))
        f = tk.Frame(frm, bg=C['bg4'])
        f.pack(fill='x')
        tk.Label(f, text=txt, font=(FONT,9,'bold'),
                 bg=C['bg4'], fg=acc, padx=14, pady=7).pack(side='left')
        tk.Frame(frm, bg=acc, height=2).pack(fill='x')
        return frm

    def _lrow(self, frm, label, wfn, tooltip=""):
        f = tk.Frame(frm, bg=C['bg2']); f.pack(fill='x', padx=16, pady=3)
        lbl = tk.Label(f, text=label, font=(FONT,9), bg=C['bg2'], fg=C['text'],
                       width=30, anchor='w')
        lbl.pack(side='left')
        if tooltip:
            self._tooltip(lbl, tooltip)
        w = wfn(f); w.pack(side='left')
        return w

    def _tooltip(self, widget, text):
        def enter(event):
            tip = tk.Toplevel(widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{event.x_root+15}+{event.y_root+10}")
            label = tk.Label(tip, text=text, background=C['bg4'], foreground=C['text'],
                             font=(FONT,8), relief='solid', borderwidth=1,
                             padx=5, pady=2)
            label.pack()
            widget.tip = tip
        def leave(event):
            if hasattr(widget, 'tip'):
                widget.tip.destroy()
                del widget.tip
        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)

    def _sp(self, parent, var, lo, hi):
        return tk.Spinbox(parent, from_=lo, to=hi, textvariable=var, width=8,
                          font=(FONT,9), bg=C['bg3'], fg=C['text'], relief='flat',
                          buttonbackground=C['bg4'], insertbackground=C['text'])

    def _pick_excel_file(self):
        if filedialog is None:
            messagebox.showwarning(
                "Seletor indisponivel",
                "O seletor de arquivos nao esta disponivel nesta versao do executavel.\n\nDigite o caminho do Excel manualmente no campo."
            )
            return ""
        restore_self = False
        restore_master = False
        try:
            restore_self = bool(self.attributes('-topmost'))
        except Exception:
            restore_self = False
        try:
            restore_master = bool(self.master.attributes('-topmost'))
        except Exception:
            restore_master = False

        try:
            if restore_self:
                self.attributes('-topmost', False)
            if restore_master:
                self.master.attributes('-topmost', False)
            self.lift()
            self.focus_force()
            self.update_idletasks()
            return filedialog.askopenfilename(parent=self, filetypes=[('Excel', '*.xlsx')])
        finally:
            try:
                if restore_master and self.master.winfo_exists():
                    self.master.attributes('-topmost', True)
                    self.master.lift()
            except Exception:
                pass
            try:
                if restore_self and self.winfo_exists():
                    self.attributes('-topmost', True)
                    self.lift()
                    self.focus_force()
            except Exception:
                pass

    def _build_tab_geral(self, tab):
        frm = tab._inner
        self._sec(tab, '📁  Arquivo de Histórico de Lances', C['cyan'])
        f = tk.Frame(frm, bg=C['bg2']); f.pack(fill='x', padx=16, pady=4)
        tk.Label(f, text="Lances_Master_Prime.xlsx:", font=(FONT,9),
                 bg=C['bg2'], fg=C['text'], width=30, anchor='w').pack(side='left')
        self.var_hist = tk.StringVar(value=CONFIG.get('historico',''))
        e = tk.Entry(f, textvariable=self.var_hist, width=38, font=(FONT,8),
                     bg=C['bg3'], fg=C['text'], relief='flat', insertbackground=C['text'])
        e.pack(side='left')
        tk.Button(f, text=' … ', font=(FONT,8), bg=C['bg4'], fg=C['text'], relief='flat',
                  cursor='hand2',
                  command=lambda: (p:=self._pick_excel_file()) and self.var_hist.set(p)
                  ).pack(side='left', padx=3)

        self._sec(tab, '🔄  Atualização Automática', C['cyan'])
        self.v_reload = tk.IntVar(value=CONFIG.get('reload_intervalo',300))
        self._lrow(frm, "Releitura automática (seg):",
                   lambda p: self._sp(p, self.v_reload, 30, 3600),
                   "Intervalo entre recargas automáticas (ignorado se tempo real ativo)")

        # 🖥️ Seletor de monitor
        self._sec(tab, '🖥️  Seleção de Monitor', C['cyan'])
        monitors = get_monitors_windows()
        if monitors:
            monitor_names = [f"Monitor {i} - {m['device']} ({m['width']}x{m['height']})" for i, m in enumerate(monitors)]
            self.monitor_names = monitor_names
            default_idx = CONFIG.get('monitor_index', 0)
            if default_idx >= len(monitor_names):
                default_idx = 0
            self.v_monitor = tk.StringVar(value=monitor_names[default_idx])
            self.cb_monitor = ttk.Combobox(frm, values=monitor_names, textvariable=self.v_monitor,
                                           font=(FONT,9), state='readonly', width=50)
            self.cb_monitor.pack(anchor='w', padx=16, pady=6)
            tk.Label(frm, text="Selecione em qual monitor o dashboard deve ser exibido",
                     font=(FONT,7,'italic'), bg=C['bg2'], fg=C['text3']).pack(anchor='w', padx=16, pady=(0,10))
        else:
            tk.Label(frm, text="Nenhum monitor adicional detectado. O dashboard usará o monitor padrão.",
                     font=(FONT,8), bg=C['bg2'], fg=C['orange']).pack(anchor='w', padx=16, pady=6)

        self._sec(tab, '🔍  Zoom da Interface', C['cyan'])
        self.v_ui_scale = tk.DoubleVar(value=CONFIG.get('ui_scale', 1.0))
        sf = tk.Frame(frm, bg=C['bg2']); sf.pack(fill='x', padx=16, pady=6)
        tk.Label(sf, text="Escala geral:", font=(FONT,9),
                 bg=C['bg2'], fg=C['text'], width=30, anchor='w').pack(side='left')
        tk.Label(sf, text="−", font=(FONT,9), bg=C['bg2'], fg=C['text2']).pack(side='left')
        sl = tk.Scale(sf, from_=0.7, to=1.5, resolution=0.05, orient='horizontal',
                      length=220, variable=self.v_ui_scale,
                      bg=C['bg2'], fg=C['text'], troughcolor=C['bg4'],
                      highlightthickness=0, sliderrelief='flat')
        sl.pack(side='left', padx=6)
        tk.Label(sf, text="+", font=(FONT,13,'bold'), bg=C['bg2'], fg=C['text2']).pack(side='left')
        self.lbl_ui_scale = tk.Label(sf, text=f"{self.v_ui_scale.get():.2f}×",
                                     font=(FONT,10,'bold'), bg=C['bg2'], fg=C['cyan'], width=6)
        self.lbl_ui_scale.pack(side='left', padx=8)
        self.v_ui_scale.trace('w', lambda *_: self.lbl_ui_scale.config(text=f"{self.v_ui_scale.get():.2f}×"))

        self._sec(tab, '⏱️  Tempo Real (Polling)', C['cyan'])
        self.v_real_time = tk.BooleanVar(value=CONFIG.get('real_time', False))
        chk = tk.Checkbutton(frm, text="Monitorar arquivos a cada 2 segundos e recarregar automaticamente",
                             variable=self.v_real_time, font=(FONT,9),
                             bg=C['bg2'], fg=C['text'], selectcolor=C['bg2'],
                             activebackground=C['bg2'], activeforeground=C['cyan'])
        chk.pack(anchor='w', padx=16, pady=6)
        tk.Label(frm, text="* Detecta mudanças nos arquivos Excel e atualiza o dashboard quase instantaneamente",
                 font=(FONT,7,'italic'), bg=C['bg2'], fg=C['text3']).pack(anchor='w', padx=16, pady=(0,10))

    def _build_tab_cat(self, tab, cat, acc):
        frm   = tab._inner
        cfg   = CONFIG[cat]
        faixas_cat = FAIXAS[cat]

        self._sec(tab, f'📁  Arquivo de Vagas', acc)
        f = tk.Frame(frm, bg=C['bg2']); f.pack(fill='x', padx=16, pady=4)
        tk.Label(f, text="Arquivo (.xlsx):", font=(FONT,9),
                 bg=C['bg2'], fg=C['text'], width=20, anchor='w').pack(side='left')
        var = tk.StringVar(value=cfg.get('arquivo',''))
        setattr(self, f'var_arq_{cat}', var)
        e = tk.Entry(f, textvariable=var, width=40, font=(FONT,8),
                     bg=C['bg3'], fg=C['text'], relief='flat', insertbackground=C['text'])
        e.pack(side='left')
        tk.Button(f, text=' … ', font=(FONT,8), bg=C['bg4'], fg=C['text'], relief='flat',
                  cursor='hand2',
                  command=lambda v=var: (p:=self._pick_excel_file()) and v.set(p)
                  ).pack(side='left', padx=3)

        self._sec(tab, '🔎  Filtros', acc)
        v_min = tk.IntVar(value=cfg.get('min_meses',0))
        v_max = tk.IntVar(value=cfg.get('max_meses',999))
        v_max_vagas = tk.IntVar(value=cfg.get('max_vagas_livres',200))
        setattr(self, f'v_minm_{cat}', v_min)
        setattr(self, f'v_maxm_{cat}', v_max)
        setattr(self, f'v_maxv_{cat}', v_max_vagas)
        self._lrow(frm, "Mínimo meses restantes:", lambda p,v=v_min: self._sp(p,v,0,999),
                   "Exibe apenas grupos com pelo menos X meses restantes")
        self._lrow(frm, "Máximo meses restantes:", lambda p,v=v_max: self._sp(p,v,0,999),
                   "Exibe apenas grupos com no máximo X meses restantes")
        self._lrow(frm, "Máximo de vagas livres (≤):", lambda p,v=v_max_vagas: self._sp(p,v,0,600),
                   "Exibe apenas grupos com até X vagas disponíveis (calculado como Total - Ocupadas)")

        fxf = tk.Frame(frm, bg=C['bg2']); fxf.pack(fill='x', padx=16, pady=4)
        tk.Label(fxf, text="Faixas de crédito:", font=(FONT,9),
                 bg=C['bg2'], fg=C['text'], width=30, anchor='w').pack(side='left')
        fv = {}
        active = cfg.get('faixas') or faixas_cat
        for fx in faixas_cat:
            v = tk.BooleanVar(value=fx in active)
            tk.Checkbutton(fxf, text=fx, variable=v, font=(FONT,8),
                           bg=C['bg2'], fg=C['text'], activebackground=C['bg2'],
                           selectcolor=C['bg3'],
                           activeforeground=acc).pack(side='left', padx=4)
            fv[fx] = v
        setattr(self, f'fv_{cat}', fv)

        self._sec(tab, '🔄  Rotação', acc)
        v_sim = tk.IntVar(value=cfg.get('vagas_simultaneas',2))
        v_rot = tk.IntVar(value=cfg.get('rotacao_intervalo',12))
        setattr(self, f'v_sim_{cat}', v_sim)
        setattr(self, f'v_rot_{cat}', v_rot)
        self._lrow(frm, "Vagas simultâneas (recomendado 2):", lambda p,v=v_sim: self._sp(p,v,1,8),
                   "Quantos cards de vagas (não favoritas) aparecem ao mesmo tempo. Para 1 favorito + N, use N=2.")
        self._lrow(frm, "Intervalo rotação (seg):", lambda p,v=v_rot: self._sp(p,v,3,120),
                   "Tempo entre cada rotação das vagas simultâneas")

        self._sec(tab, '⭐  Favoritos', acc)
        ff = tk.Frame(frm, bg=C['bg2']); ff.pack(fill='x', padx=16, pady=6)
        tk.Label(ff, text="Um grupo por linha  (ex: AF477) – apenas o primeiro será exibido",
                 font=(FONT,8,'italic'), bg=C['bg2'], fg=C['text3']).pack(anchor='w')
        txt = tk.Text(ff, height=5, width=22, font=(FONT,9),
                      bg=C['bg3'], fg=C['text'], relief='flat',
                      insertbackground=C['text'], selectbackground=C['blue'])
        txt.pack(fill='x', pady=4)
        txt.insert('1.0', '\n'.join(cfg.get('favoritos',[])))
        setattr(self, f'txt_fav_{cat}', txt)

    def _collect(self):
        CONFIG['historico']        = self.var_hist.get()
        CONFIG['reload_intervalo'] = self.v_reload.get()
        # 🖥️ Salvar monitor selecionado (converte texto para índice)
        if hasattr(self, 'v_monitor'):
            selected_text = self.v_monitor.get()
            try:
                idx = self.monitor_names.index(selected_text)
            except ValueError:
                idx = 0
            CONFIG['monitor_index'] = idx
        CONFIG['ui_scale']         = round(self.v_ui_scale.get(), 2)
        CONFIG['real_time']        = self.v_real_time.get()
        CONFIG['font_scale']       = CONFIG['ui_scale']

        for cat in ['auto','imovel','pesado']:
            faixas_cat = FAIXAS[cat]
            CONFIG[cat]['arquivo']          = getattr(self, f'var_arq_{cat}').get()
            CONFIG[cat]['min_meses']        = getattr(self, f'v_minm_{cat}').get()
            CONFIG[cat]['max_meses']        = getattr(self, f'v_maxm_{cat}').get()
            CONFIG[cat]['max_vagas_livres'] = getattr(self, f'v_maxv_{cat}').get()
            CONFIG[cat]['vagas_simultaneas']= getattr(self, f'v_sim_{cat}').get()
            CONFIG[cat]['rotacao_intervalo']= getattr(self, f'v_rot_{cat}').get()
            fv  = getattr(self, f'fv_{cat}')
            sel = [f for f,v in fv.items() if v.get()]
            CONFIG[cat]['faixas'] = [] if len(sel)==len(faixas_cat) else sel
            raw = getattr(self, f'txt_fav_{cat}').get('1.0','end').strip().splitlines()
            CONFIG[cat]['favoritos'] = [g.strip().upper() for g in raw if g.strip()]

    def _apply(self):
        self._collect(); CONFIG['_dirty'] = True
        if hasattr(self, 'v_monitor'):
            self.master._apply_monitor_settings()
        self.lbl_ok.config(text="✔  Aplicado!", fg=C['green'])
        self.after(2500, lambda: self.lbl_ok.config(text=''))

    def _apply_reload(self):
        self._collect(); CONFIG['_dirty'] = True; CONFIG['_reload_now'] = True
        if hasattr(self, 'v_monitor'):
            self.master._apply_monitor_settings()
        self.lbl_ok.config(text="✔  Aplicado – relendo xlsx...", fg=C['green'])
        self.after(2500, lambda: self.lbl_ok.config(text=''))

    def _save(self):
        self._collect()
        cfg_save = {k:v for k,v in CONFIG.items() if not k.startswith('_')}
        ok = save_config(cfg_save)
        self.lbl_ok.config(
            text="💾  Salvo!" if ok else "❌  Erro ao salvar",
            fg=C['green'] if ok else 'red'
        )
        self.after(3000, lambda: self.lbl_ok.config(text=''))

if __name__ == '__main__':
    root = tk.Tk()
    root.withdraw()
    app = DashboardTV(master=root, keep_on_top=True, exit_on_close=True)
    root.mainloop()
