import os
import json
import pandas as pd
from flask import Flask, jsonify, render_template, send_from_directory, request
import re
from datetime import datetime
import threading
import time
import sys
import subprocess
import socket

# Importar lógica do extrator
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

try:
    import extrator_porto_seguro as extrator
except Exception as e:
    print("\n" + "="*50)
    print("ERRO CRÍTICO NA IMPORTAÇÃO DO EXTRATOR:")
    print(e)
    import traceback
    traceback.print_exc()
    print("="*50 + "\n")
    extrator = None

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "dashboard_config.json")
EXCEL_DIR = BASE_DIR

EXTRATOR_STATUS = {
    "rodando": False,
    "ultimo_log": "Aguardando início...",
    "progresso": 0,
    "ultima_atualizacao": None
}

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
    try:
        xl = pd.ExcelFile(path)
        for sheet in FAIXAS.get(categoria, []):
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
    except Exception as e:
        print(f"Erro lendo vagas {categoria}: {e}")
        return pd.DataFrame()

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

CACHE = {}
LAST_UPDATE = {}

def get_data():
    now = datetime.now()
    config = load_config()
    historico_path = config.get('historico', os.path.join(BASE_DIR, 'Lances Master Prime.xlsx'))
    if 'historico' not in CACHE or (now - LAST_UPDATE.get('historico', datetime.min)).total_seconds() > 30:
        CACHE['historico'] = load_historico(historico_path)
        LAST_UPDATE['historico'] = now
    vagas = {}
    for cat in ['auto', 'imovel', 'pesado']:
        default_file = os.path.join(BASE_DIR, f'vagas_{"automoveis" if cat=="auto" else "imoveis" if cat=="imovel" else "veiculos_pesados"}.xlsx')
        path = config.get(cat, {}).get('arquivo', default_file)
        if cat not in CACHE or (now - LAST_UPDATE.get(cat, datetime.min)).total_seconds() > 30:
            CACHE[cat] = load_vagas(path, cat)
            LAST_UPDATE[cat] = now
        df = CACHE[cat]
        cat_config = config.get(cat, {})
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

@app.route('/api/status')
def api_status():
    return jsonify(EXTRATOR_STATUS)

@app.route('/api/extrair', methods=['POST'])
def api_extrair():
    if EXTRATOR_STATUS["rodando"]:
        return jsonify({"error": "Extrator já está rodando"}), 400
    dados = request.json or {}
    usuario = dados.get("usuario")
    senha = dados.get("senha")
    if not usuario or not senha:
        cfg = extrator.carregar_config()
        usuario = usuario or cfg.get("usuario")
        senha = senha or cfg.get("senha")
    if not usuario or not senha:
        return jsonify({"error": "Usuário e senha são obrigatórios"}), 400
    thread = threading.Thread(target=executar_extracao_background, args=(usuario, senha))
    thread.start()
    return jsonify({"message": "Extração iniciada em background"})

def log_web(msg):
    print(f"[EXTRATOR] {msg}")
    EXTRATOR_STATUS["ultimo_log"] = msg
    EXTRATOR_STATUS["ultima_atualizacao"] = datetime.now().strftime("%H:%M:%S")

def executar_extracao_background(usuario, senha):
    if not extrator:
        log_web("Erro: Módulo extrator não encontrado")
        return
    EXTRATOR_STATUS["rodando"] = True
    EXTRATOR_STATUS["progresso"] = 0
    log_web("Iniciando extrator...")
    driver = None
    try:
        config = extrator.carregar_config()
        config["usuario"] = usuario
        config["senha"] = senha
        log_web("Configurando navegador...")
        driver = extrator.configurar_navegador(exibir_janela=False)
        wait = extrator.WebDriverWait(driver, extrator.TIMEOUT)
        log_web("Fazendo login...")
        extrator.fazer_login(driver, wait, log_web, config)
        tipos = ["Automoveis", "Veiculos pesados", "Imoveis"]
        total_passos = sum(len(extrator.FAIXAS_REAIS[t]) for t in tipos)
        passo_atual = 0
        for tipo_chave in tipos:
            faixas = extrator.FAIXAS_REAIS[tipo_chave]
            tipo_real = extrator.TIPOS_REAIS[tipo_chave]
            log_web(f"Extraindo {tipo_real}...")
            abas = []
            for faixa in faixas:
                cabecalho, linhas = extrator.acessar_simulador_faixa(driver, wait, log_web, tipo_chave, faixa)
                nome_aba = faixa.replace("De R$ ", "").replace(" até R$ ", "-").replace(".", "").replace(",00", "")
                abas.append((nome_aba, cabecalho, linhas))
                passo_atual += 1
                EXTRATOR_STATUS["progresso"] = int((passo_atual / total_passos) * 100)
            nome_arquivo = os.path.join(BASE_DIR, f"vagas_{tipo_chave.lower().replace(' ', '_')}.xlsx")
            extrator.salvar_excel(abas, log_web, arquivo=nome_arquivo)
        log_web("Extração concluída com sucesso!")
    except Exception as e:
        log_web(f"Erro durante extração: {str(e)}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        EXTRATOR_STATUS["rodando"] = False
        EXTRATOR_STATUS["progresso"] = 100

@app.route('/api/config', methods=['GET'])
def api_get_config():
    try:
        config = load_config()
        for cat in ['auto', 'imovel', 'pesado']:
            default_file = os.path.join(BASE_DIR, f'vagas_{"automoveis" if cat=="auto" else "imoveis" if cat=="imovel" else "veiculos_pesados"}.xlsx')
            path = config.get(cat, {}).get('arquivo', default_file)
            if cat not in config:
                config[cat] = {}
            config[cat]['arquivo_atual'] = path
            config[cat]['arquivo_existe'] = os.path.exists(path)
        historico_path = config.get('historico', os.path.join(BASE_DIR, 'Lances Master Prime.xlsx'))
        config['historico_path'] = historico_path
        config['historico_existe'] = os.path.exists(historico_path)
        config['base_dir'] = BASE_DIR
        return jsonify(config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['POST'])
def api_save_config():
    try:
        new_config = request.json or {}
        existing = load_config()
        for key, val in new_config.items():
            if isinstance(val, dict) and isinstance(existing.get(key), dict):
                existing[key].update(val)
            else:
                existing[key] = val
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        CACHE.clear()
        LAST_UPDATE.clear()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/grupos')
def api_grupos():
    try:
        data = get_data()
        grupos = {}
        for cat in ['auto', 'imovel', 'pesado']:
            df_list = data['vagas'][cat]
            grupos[cat] = []
            for row in df_list:
                grupo = row.get('Grupo', '')
                meses = row.get('_meses', 0)
                faixa = row.get('Faixa', '')
                if grupo:
                    grupos[cat].append({'grupo': grupo, 'meses': meses, 'faixa': faixa})
        return jsonify(grupos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================================
# 🔹 CONTROLE AUTOMÁTICO DA TV (ROBUSTO - GARANTE FOCO E ROLAGEM) 🔹
# =============================================================================

ADB_PATH = "C:\\platform-tools\\adb.exe"

def descobrir_firestick():
    try:
        resultado = subprocess.run([ADB_PATH, "devices"], capture_output=True, text=True, timeout=10)
        linhas = resultado.stdout.strip().split('\n')
        for linha in linhas[1:]:
            if 'device' in linha and 'offline' not in linha:
                ip_port = linha.split('\t')[0].strip()
                if ':' in ip_port:
                    return ip_port.split(':')[0]
    except Exception as e:
        print(f"[TV] Erro ao descobrir Firestick: {e}")
    return None

def executar_comando_adb(comando, timeout=30):
    comando_completo = f"{ADB_PATH} {comando}"
    try:
        resultado = subprocess.run(
            comando_completo,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        return resultado.returncode == 0, resultado.stdout.strip(), resultado.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", f"timeout após {timeout}s"
    except Exception as e:
        return False, "", str(e)

def conectar_firestick(ip):
    sucesso, stdout, stderr = executar_comando_adb(f"connect {ip}:5555", timeout=10)
    if sucesso and ('connected' in stdout.lower() or 'already connected' in stdout.lower()):
        return True
    return False

def configurar_tv():
    time.sleep(8)

    print("[TV] Procurando Firestick na rede...")
    firestick_ip = descobrir_firestick()
    if not firestick_ip:
        firestick_ip = "192.168.1.166"
        print(f"[TV] Usando IP padrão: {firestick_ip}")
    else:
        print(f"[TV] Firestick encontrado em: {firestick_ip}")

    URL_DASHBOARD = "http://192.168.1.28:8888"

    conectado = False
    for tentativa in range(1, 4):
        print(f"[TV] Tentativa {tentativa} de conectar a {firestick_ip}...")
        if conectar_firestick(firestick_ip):
            print("[TV] Conectado com sucesso!")
            conectado = True
            break
        time.sleep(5)
    if not conectado:
        print("[TV] Não foi possível conectar.")
        return

    print("[TV] Ligando TV via HOME...")
    executar_comando_adb("shell input keyevent KEYCODE_HOME", timeout=10)
    time.sleep(3)
    executar_comando_adb("shell input keyevent KEYCODE_POWER", timeout=5)
    time.sleep(2)

    print("[TV] Tentando selecionar HDMI 1...")
    executar_comando_adb("shell input keyevent HDMI1", timeout=5)
    time.sleep(2)

    print("[TV] Abrindo dashboard...")
    comando_padrao = f"shell am start -a android.intent.action.VIEW -d \"{URL_DASHBOARD}\""
    sucesso, _, stderr = executar_comando_adb(comando_padrao, timeout=15)
    if not sucesso or 'error' in stderr.lower():
        print("[TV] Padrão falhou, tentando Amazon Silk...")
        comando_silk = f"shell am start -n com.amazon.cloud9/.BrowserActivity -a android.intent.action.VIEW -d \"{URL_DASHBOARD}\" --ei android.intent.extra.TIME 1"
        sucesso, _, stderr = executar_comando_adb(comando_silk, timeout=15)
        if not sucesso:
            print(f"[TV] Erro ao abrir: {stderr}")
            return
    print("[TV] Dashboard aberto!")

    # --- Aguarda e força o foco ---
    print("[TV] Aguardando 15 segundos para carregamento...")
    time.sleep(15)

    # Toques múltiplos em posições diferentes para garantir foco no conteúdo
    print("[TV] Garantindo foco na página (toques)...")
    for pos in [(550, 350), (550, 600), (550, 800), (960, 540), (300, 500)]:
        executar_comando_adb(f"shell input tap {pos[0]} {pos[1]}", timeout=5)
        time.sleep(0.5)

    # Envia PAGE_DOWN algumas vezes (funciona mesmo sem foco perfeito)
    print("[TV] Enviando PAGE_DOWN para rolar...")
    for _ in range(5):
        executar_comando_adb("shell input keyevent KEYCODE_PAGE_DOWN", timeout=5)
        time.sleep(0.3)

    # Agora simula o pressionamento longo do botão para baixo
    print("[TV] Simulando botão para baixo pressionado (500 comandos)...")
    for _ in range(500):
        executar_comando_adb("shell input keyevent KEYCODE_DPAD_DOWN", timeout=2)
        time.sleep(0.01)

    # Se ainda não rolou o suficiente, reforça com mais 200 comandos
    print("[TV] Reforçando rolagem...")
    for _ in range(200):
        executar_comando_adb("shell input keyevent KEYCODE_DPAD_DOWN", timeout=2)
        time.sleep(0.01)

    # Por fim, envia mais alguns PAGE_DOWN para garantir
    for _ in range(3):
        executar_comando_adb("shell input keyevent KEYCODE_PAGE_DOWN", timeout=5)
        time.sleep(0.2)

    print("[TV] Rolagem concluída.")

# =============================================================================

if __name__ == '__main__':
    threading.Thread(target=configurar_tv, daemon=True).start()
    app.run(host='0.0.0.0', port=8888, debug=False, threaded=True)