import os
import json
import pandas as pd
from flask import Flask, jsonify, render_template, send_from_directory, request
import re
from datetime import datetime

app = Flask(__name__)

# Diretório base
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "dashboard_config.json")
EXCEL_DIR = BASE_DIR

FAIXAS = {
    'auto':   ['25000-50000', '34000-65000', '62500-125000', '125000-200000'],
    'imovel': ['70000-140000', '140000-280000', '280000-560000', '600000-900000', '900000-1000000'],
    'pesado': ['180000-360000'],
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def _find_column(df, possible_names):
    for col in df.columns:
        col_lower = col.lower().strip()
        for name in possible_names:
            if name.lower() in col_lower:
                return col
    return None

def load_vagas(path, categoria):
    if not os.path.exists(path):
        return pd.DataFrame()
    frames = []
    xl = pd.ExcelFile(path)
    for sheet in FAIXAS.get(categoria, []):
        if sheet in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet, header=0)
            df['Faixa'] = sheet
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    df_all = pd.concat(frames, ignore_index=True)
    
    # Calcular meses restantes
    df_all['_meses'] = df_all['Meses restantes'].astype(str).str.extract(r'(\d+)')[0].astype(float)
    
    # Calcular vagas livres
    vagas_col = _find_column(df_all, ['vagas/participantes', 'vagas / participantes', 'vagas', 'participantes'])
    if vagas_col is None:
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

    return df_all.fillna('')

def load_historico(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    def melt_sheet(xl, sheet, val):
        df = pd.read_excel(xl, sheet_name=sheet, header=3)
        cols = [c for c in df.columns if c not in ('CD_Grupo', 'Total Geral')]
        df['CD_Grupo'] = df['CD_Grupo'].astype(str).str.strip().str.upper()
        m = df[['CD_Grupo'] + cols].melt(id_vars='CD_Grupo', var_name='Mes', value_name=val)
        return m.dropna(subset=[val])
    try:
        xl = pd.ExcelFile(path)
        df = (melt_sheet(xl, 'MinPS',  'Lance_Min')
              .merge(melt_sheet(xl, 'MaxPS',  'Lance_Max'),  on=['CD_Grupo','Mes'])
              .merge(melt_sheet(xl, 'ContPS', 'QT_Contemp'), on=['CD_Grupo','Mes']))
        df['Mes'] = pd.to_datetime(df['Mes'], errors='coerce')
        df = df.dropna(subset=['Mes'])
        for c in ['Lance_Min','Lance_Max','QT_Contemp']:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        return df.dropna().sort_values('Mes')
    except Exception as e:
        print(f"Erro lendo historico: {e}")
        return pd.DataFrame()

# Cache em memoria (simples)
CACHE = {}
LAST_UPDATE = {}

def get_data():
    now = datetime.now()
    config = load_config()
    historico_path = config.get('historico', os.path.join(BASE_DIR, 'Lances Master Prime (2) (1).xlsx'))
    
    # Verificar se cache expirou (a cada 30 segundos)
    if 'historico' not in CACHE or (now - LAST_UPDATE.get('historico', datetime.min)).total_seconds() > 30:
        CACHE['historico'] = load_historico(historico_path)
        LAST_UPDATE['historico'] = now

    vagas = {}
    for cat in ['auto', 'imovel', 'pesado']:
        # Arquivo padrão caso não esteja no config
        default_file = os.path.join(BASE_DIR, f'vagas_{"automoveis" if cat=="auto" else "imoveis" if cat=="imovel" else "veiculos_pesados"}.xlsx')
        path = config.get(cat, {}).get('arquivo', default_file)
        if cat not in CACHE or (now - LAST_UPDATE.get(cat, datetime.min)).total_seconds() > 30:
            CACHE[cat] = load_vagas(path, cat)
            LAST_UPDATE[cat] = now
            
        df = CACHE[cat]
        cat_config = config.get(cat, {})
        # Filtros
        if not df.empty:
            mn, mx = cat_config.get('min_meses', 0), cat_config.get('max_meses', 999)
            if mn > 0: df = df[df['_meses'] >= mn]
            if mx < 999: df = df[df['_meses'] <= mx]
            
            max_vagas = cat_config.get('max_vagas_livres', 200)
            if max_vagas > 0 and '_vagas_livres' in df.columns:
                df['_vagas_livres'] = pd.to_numeric(df['_vagas_livres'], errors='coerce').fillna(0)
                df = df[df['_vagas_livres'] <= max_vagas]
                
            faixas = cat_config.get('faixas', [])
            if faixas:
                df = df[df['Faixa'].isin(faixas)]
                
            df = df.drop_duplicates(subset='Grupo', keep='first').reset_index(drop=True)
            
        vagas[cat] = df.to_dict(orient='records')
        
    return {
        'vagas': vagas,
        'historico': CACHE['historico'].to_dict(orient='records') if not CACHE['historico'].empty else [],
        'config': config
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def api_data():
    try:
        data = get_data()
        
        # O historico pode ser grande, entao enviamos apenas o agrupado por grupo
        hist = data['historico']
        hist_by_group = {}
        for row in hist:
            g = row['CD_Grupo']
            if g not in hist_by_group:
                hist_by_group[g] = []
            hist_by_group[g].append({
                'Mes': row['Mes'].strftime('%Y-%m-%d'),
                'Lance_Min': row['Lance_Min'],
                'Lance_Max': row['Lance_Max'],
                'QT_Contemp': row['QT_Contemp']
            })
            
        return jsonify({
            'vagas': data['vagas'],
            'historico': hist_by_group,
            'config': data['config']
        })
    except Exception as e:
        print(f"Erro /api/data: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Rodar servidor acessível na rede local, na porta 5000
    app.run(host='0.0.0.0', port=5000, debug=True)