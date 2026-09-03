import streamlit as st
import pandas as pd
import io
import zipfile
import re
import time
import os
import xml.etree.ElementTree as ET
import math
import requests
import unicodedata
import folium
from folium.plugins import HeatMap, MarkerCluster, MeasureControl, Draw
import gc
from streamlit_folium import st_folium
import html
from concurrent.futures import ThreadPoolExecutor
from scipy.spatial import cKDTree
import plotly.express as px
import sqlite3
import json
import hashlib
from datetime import datetime

st.set_page_config(page_title="Gestão de Malha e Projetos", page_icon="🗺️", layout="wide")

# ==========================================
# 1. MOTOR DE BANCO DE DADOS (SQLITE MIGRATION)
# ==========================================
def init_db_and_migrate():
    if not os.path.exists("database"):
        os.makedirs("database", exist_ok=True)

    conn = sqlite3.connect("database/redes.db")
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS malha (ALIMENTADOR TEXT, REGIONAL TEXT, MUNICIPIO TEXT, TIPO_GEOMETRIA TEXT, TIPO_REDE TEXT, NOME TEXT, COORDS TEXT, COR TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS arquivos_kmz (ALIMENTADOR TEXT PRIMARY KEY, ARQUIVO TEXT, HASH_SHA256 TEXT, TAMANHO INTEGER, MTIME_NS INTEGER, PROCESSADO_EM TEXT)')
    conn.commit()

    if os.path.exists("database/redes"):
        pkl_files = [f for f in os.listdir("database/redes") if f.endswith('.pkl')]
        for f in pkl_files:
            try:
                caminho_pkl = f"database/redes/{f}"
                df_pkl = pd.read_pickle(caminho_pkl)
                df_pkl['COORDS'] = df_pkl['COORDS'].apply(json.dumps)
                df_pkl.to_sql('malha', conn, if_exists='append', index=False)
                os.remove(caminho_pkl)
            except Exception:
                pass
    conn.close()

init_db_and_migrate()

# ==========================================
# 2. FUNÇÕES BASE, PLANILHA E GEOLOCALIZAÇÃO
# ==========================================
def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', str(input_str))
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])

def latlon_to_xyz(lat, lon):
    R = 6371000.0
    lat_rad, lon_rad = math.radians(lat), math.radians(lon)
    return R * math.cos(lat_rad) * math.cos(lon_rad), R * math.cos(lat_rad) * math.sin(lon_rad), R * math.sin(lat_rad)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2.0)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2.0)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

@st.cache_data(show_spinner=False)
def load_base_mapping():
    mun_to_reg = {}
    file_path = "MUNICIPIOS-REGIONAIS.xlsx"
    if not os.path.exists(file_path):
        st.sidebar.error(f"🚨 Planilha '{file_path}' não encontrada!")
    else:
        try:
            df_base = pd.read_excel(file_path)
            for _, row in df_base.iterrows():
                mun = remove_accents(str(row.get('MunicIpio', ''))).upper().strip()
                reg = str(row.get('Regional', '')).strip().upper()
                if mun and reg and reg != 'NAN': mun_to_reg[mun] = reg
        except Exception as e: st.sidebar.error(f"🚨 Erro: {e}")
    
    overrides_centro = ['SANTA LUZIA', 'CONCEICAO DO LAGO-ACU', 'CONCEICAO DO LAGO ACU', 'PINDARE-MIRIM', 'PINDARE MIRIM', 'OLHO DAGUA DAS CUNHAS', 'OLHO D\'AGUA DAS CUNHAS', 'GOVERNADOR LUIZ ROCHA']
    for mun in overrides_centro:
        if mun not in mun_to_reg: mun_to_reg[mun] = 'CENTRO'
    return mun_to_reg

@st.cache_data(show_spinner=False)
def get_base_geojson():
    # Carrega a divisão municipal do MA com cache local para preservar as cores regionais.
    mun_to_reg = load_base_mapping()
    url_geojson = "https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-21-mun.json"
    cache_path = "database/geojs-21-mun.json"
    geo_data = None

    # Cache local primeiro: depois do primeiro acesso, a abertura do mapa não espera internet.
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                geo_data = json.load(f)
        except Exception:
            geo_data = None

    if geo_data is None:
        try:
            resp = requests.get(url_geojson, headers={'User-Agent': 'Mozilla/5.0'}, timeout=2.5)
            resp.raise_for_status()
            geo_data = resp.json()
            try:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(geo_data, f, ensure_ascii=False)
            except Exception:
                pass
        except Exception:
            geo_data = None

    if not geo_data:
        return None

    reg_colors = {
        'LESTE': '#1f77b4',
        'CENTRO': '#d62728',
        'NOROESTE': '#ffed6f',
        'NORTE': '#ff7f0e',
        'SUL': '#8fbc8f',
        'DESCONHECIDO': '#9ca3af',
    }
    for feature in geo_data.get('features', []):
        mun_name = feature.get('properties', {}).get('name', '')
        mun_name_norm = remove_accents(mun_name).upper().strip()
        reg = mun_to_reg.get(mun_name_norm, "DESCONHECIDO")
        feature.setdefault('properties', {})['REGIONAL'] = reg
        feature['properties']['MUNICIPIO'] = mun_name_norm
        feature['properties']['fillColor'] = reg_colors.get(reg, '#9ca3af')
    return geo_data

def is_point_in_polygon(lon, lat, polygon):
    inside = False
    for i in range(len(polygon)):
        p1x, p1y = polygon[i]
        p2x, p2y = polygon[(i + 1) % len(polygon)]
        if ((p1y > lat) != (p2y > lat)) and (lon < (p2x - p1x) * (lat - p1y) / (p2y - p1y + 1e-9) + p1x): inside = not inside
    return inside

def extrair_coordenadas_vis(texto_coords):
    pontos = []
    for coord in texto_coords.strip().split():
        partes = coord.split(',')
        if len(partes) >= 2:
            try:
                lon = float(partes[0].strip().replace(',', '.'))
                lat = float(partes[1].strip().replace(',', '.'))
                if lat != 0.0 and lon != 0.0 and -35.0 <= lat <= 5.0 and -75.0 <= lon <= -30.0: pontos.append([lat, lon]) 
            except: continue
    return pontos

def ler_kml_para_geojson(caminho_arquivo, cor_hex):
    if not os.path.exists(caminho_arquivo): return None
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f: kml_str = f.read()
        kml_str = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', kml_str)
        root = ET.fromstring(kml_str)
        features = []
        for placemark in root.findall('.//Placemark'):
            name_tag = placemark.find('name')
            nome = name_tag.text.strip() if name_tag is not None and name_tag.text else "Área Demarcada"
            for poly in placemark.findall('.//Polygon//coordinates'):
                if poly.text:
                    coords = []
                    for coord_str in poly.text.strip().split():
                        partes = coord_str.split(',')
                        if len(partes) >= 2: coords.append([float(partes[0]), float(partes[1])])
                    if coords: features.append({"type": "Feature", "properties": {"NOME": nome, "COR": cor_hex}, "geometry": {"type": "Polygon", "coordinates": [coords]}})
            for pt in placemark.findall('.//Point/coordinates'):
                if pt.text:
                    partes = pt.text.strip().split(',')
                    if len(partes) >= 2: features.append({"type": "Feature", "properties": {"NOME": nome, "COR": cor_hex}, "geometry": {"type": "Point", "coordinates": [float(partes[0]), float(partes[1])]}})
        if features: return {"type": "FeatureCollection", "features": features}
        return None
    except: return None

@st.cache_data(show_spinner=False)
def get_kml_cached(path, color):
    return ler_kml_para_geojson(path, color)

# ==========================================
# PADRÃO DE CAMADAS E SIMBOLOGIA DOS KMZ
# ==========================================
TIPOS_PADRAO_VISIVEIS = {"POSTE", "TRANSFORMADOR", "REDE PRIMARIA", "REDE SECUNDARIA"}

# Limites visuais aplicados diretamente no Leaflet. Zoom e pan permanecem no navegador.
ZOOM_MIN_LINHAS = 7
ZOOM_MIN_TRANSFORMADOR = 10
ZOOM_MIN_POSTE = 12
ZOOM_MIN_EQUIPAMENTOS = 11
MAPA_CENTRO_INICIAL = (-5.2, -45.0)
MAX_ALIMENTADORES_DETALHE = 3
TIPOS_ESPERADOS_KMZ = {
    "SUBESTACAO", "RELIGADOR", "CHAVE", "TRANSFORMADOR",
    "REDE PRIMARIA", "REDE SECUNDARIA", "POSTE"
}


def _distancia_ponto_segmento(p, a, b):
    px, py = p[1], p[0]
    ax, ay = a[1], a[0]
    bx, by = b[1], b[0]
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    qx, qy = ax + t * dx, ay + t * dy
    return math.hypot(px - qx, py - qy)


def simplificar_linha(coords, tolerancia=0.0012):
    # Douglas-Peucker iterativo para não estourar a recursão em linhas grandes.
    if not coords or len(coords) <= 2:
        return coords
    keep = {0, len(coords) - 1}
    pilha = [(0, len(coords) - 1)]
    while pilha:
        ini, fim = pilha.pop()
        if fim - ini <= 1:
            continue
        a, b = coords[ini], coords[fim]
        maior_dist = 0.0
        maior_idx = None
        for i in range(ini + 1, fim):
            d = _distancia_ponto_segmento(coords[i], a, b)
            if d > maior_dist:
                maior_dist = d
                maior_idx = i
        if maior_idx is not None and maior_dist > tolerancia:
            keep.add(maior_idx)
            pilha.append((ini, maior_idx))
            pilha.append((maior_idx, fim))
    return [coords[i] for i in sorted(keep)]


@st.cache_data(show_spinner=False)
def assinatura_arquivo_kmz(caminho, tamanho, mtime_ns):
    # Hash em cache: um KMZ só é relido para hash quando tamanho ou mtime mudam.
    h = hashlib.sha256()
    with open(caminho, 'rb') as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b''):
            h.update(bloco)
    return h.hexdigest()


def carregar_assinaturas_kmz():
    try:
        conn = sqlite3.connect("database/redes.db")
        rows = conn.execute("SELECT ALIMENTADOR, HASH_SHA256, TAMANHO, MTIME_NS FROM arquivos_kmz").fetchall()
        conn.close()
        return {r[0]: {'hash': r[1], 'tamanho': r[2], 'mtime_ns': r[3]} for r in rows}
    except Exception:
        return {}


def registrar_assinatura_kmz(caminho):
    try:
        nome = os.path.basename(caminho)
        alim = nome.upper().replace('.KMZ', '').replace('.KML', '')
        stat = os.stat(caminho)
        sha = assinatura_arquivo_kmz(caminho, stat.st_size, stat.st_mtime_ns)
        conn = sqlite3.connect("database/redes.db")
        sql = ('INSERT INTO arquivos_kmz(ALIMENTADOR, ARQUIVO, HASH_SHA256, TAMANHO, MTIME_NS, PROCESSADO_EM) '
               'VALUES (?, ?, ?, ?, ?, ?) '
               'ON CONFLICT(ALIMENTADOR) DO UPDATE SET ARQUIVO=excluded.ARQUIVO, HASH_SHA256=excluded.HASH_SHA256, '
               'TAMANHO=excluded.TAMANHO, MTIME_NS=excluded.MTIME_NS, PROCESSADO_EM=excluded.PROCESSADO_EM')
        conn.execute(sql, (alim, nome, sha, stat.st_size, stat.st_mtime_ns, datetime.now().isoformat(timespec='seconds')))
        conn.commit()
        conn.close()
    except Exception:
        pass

CORES_REDE = {
    "REDE PRIMARIA": "#0066FF",      # azul
    "REDE SECUNDARIA": "#FF00FF",    # magenta
    "POSTE": "#808080",              # cinza
    "TRANSFORMADOR": "#FFD700",      # amarelo
    "CHAVE": "#3cb44b",
    "REGULADOR": "#911eb4",
    "RELIGADOR": "#46f0f0",
    "CAPACITOR": "#ffe119",
    "SUBESTACAO": "#000000",
}

ROTULOS_REDE = {
    "REDE PRIMARIA": "Rede Primária",
    "REDE SECUNDARIA": "Rede Secundária",
    "POSTE": "Poste",
    "TRANSFORMADOR": "Transformador",
    "CHAVE": "Chave",
    "REGULADOR": "Regulador",
    "RELIGADOR": "Religador",
    "CAPACITOR": "Capacitor",
    "SUBESTACAO": "Subestação",
}

def normalizar_tipo_rede(valor):
    """Normaliza o nome da pasta/camada do KML sem alterar o conteúdo original do arquivo."""
    tipo = remove_accents(str(valor)).upper().strip()
    tipo = re.sub(r'\s+', ' ', tipo)
    aliases = {
        'REDE PRIMARIA': 'REDE PRIMARIA',
        'REDE SECUNDARIA': 'REDE SECUNDARIA',
        'POSTE': 'POSTE',
        'POSTES': 'POSTE',
        'TRANSFORMADOR': 'TRANSFORMADOR',
        'TRANSFORMADORES': 'TRANSFORMADOR',
        'CHAVE': 'CHAVE',
        'CHAVES': 'CHAVE',
        'REGULADOR': 'REGULADOR',
        'REGULADORES': 'REGULADOR',
        'RELIGADOR': 'RELIGADOR',
        'RELIGADORES': 'RELIGADOR',
        'CAPACITOR': 'CAPACITOR',
        'CAPACITORES': 'CAPACITOR',
        'SUBESTACAO': 'SUBESTACAO',
        'SUBESTACOES': 'SUBESTACAO',
    }
    return aliases.get(tipo, tipo)


def processar_um_kmz(f_name, f_bytes, base_map, geo_data):
    """
    Lê o KML/KMZ sem modificar o arquivo de origem.

    Importante: os Placemark são lidos apenas da pasta imediata (./Placemark),
    evitando duplicação quando existem Folder aninhados. O código anterior usava
    .//Placemark dentro de cada Folder e podia importar o mesmo elemento várias vezes.
    """
    nome_arquivo = f_name.upper().replace('.KMZ', '').replace('.KML', '')
    conteudo_kml = ""

    if f_name.lower().endswith('.kmz'):
        try:
            with zipfile.ZipFile(io.BytesIO(f_bytes), 'r') as z:
                # Preferir doc.kml quando existir; caso contrário usar o primeiro KML.
                itens_kml = [item for item in z.namelist() if item.lower().endswith('.kml')]
                if not itens_kml:
                    return None
                item_principal = next((i for i in itens_kml if i.lower().endswith('/doc.kml') or i.lower() == 'doc.kml'), itens_kml[0])
                conteudo_kml = z.read(item_principal).decode('utf-8', errors='ignore')
        except Exception:
            return None
    else:
        try:
            conteudo_kml = f_bytes.decode('utf-8', errors='ignore')
        except Exception:
            return None

    # Remove namespaces apenas da cópia em memória. O KMZ/KML original não é regravado.
    conteudo_kml = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', conteudo_kml)
    try:
        root = ET.fromstring(conteudo_kml)
    except Exception:
        return None

    municipio, regional = "N/A", "N/A"
    mun_match = re.search(r'name=["\'](?:MUNICIPIO|CIDADE)["\'][^>]*>(.*?)</', conteudo_kml, re.IGNORECASE)
    if mun_match:
        municipio = mun_match.group(1).strip().upper()
        mun_norm = remove_accents(municipio)
        if mun_norm in base_map:
            regional = base_map[mun_norm]

    if regional == "N/A":
        reg_match = re.search(r'name=["\'](?:REGIONAL|REGIAO)["\'][^>]*>(.*?)</', conteudo_kml, re.IGNORECASE)
        if reg_match:
            regional = reg_match.group(1).strip().upper()

    if regional == "N/A":
        sigla_match = re.search(r'\[([A-Z]{3})\]', nome_arquivo)
        if sigla_match:
            regional = sigla_match.group(1)

    registros_flat = []

    # Cada divisão do KMZ é tratada pela pasta que contém diretamente os Placemark.
    # Isso preserva POSTE, TRANSFORMADOR, REDE PRIMÁRIA, REDE SECUNDÁRIA etc.
    for folder in root.findall('.//Folder'):
        name_tag = folder.find('./name')
        if name_tag is None or not name_tag.text:
            continue

        nome_pasta_original = name_tag.text.strip()
        nome_pasta = normalizar_tipo_rede(nome_pasta_original)
        if "CEMAR" in nome_pasta or nome_arquivo in nome_pasta:
            continue

        placemarks_diretos = folder.findall('./Placemark')
        if not placemarks_diretos:
            continue

        cor_elemento = CORES_REDE.get(nome_pasta, '#333333')

        for placemark in placemarks_diretos:
            pm_name_tag = placemark.find('./name')
            nome_elemento = pm_name_tag.text.strip() if pm_name_tag is not None and pm_name_tag.text else "S/N"

            for ls in placemark.findall('.//LineString/coordinates'):
                if not ls.text:
                    continue
                coords = extrair_coordenadas_vis(ls.text)
                if len(coords) > 1:
                    registros_flat.append({
                        'ALIMENTADOR': nome_arquivo,
                        'REGIONAL': regional,
                        'MUNICIPIO': municipio,
                        'TIPO_GEOMETRIA': 'Linha',
                        'TIPO_REDE': nome_pasta,
                        'NOME': nome_elemento,
                        'COORDS': coords,
                        'COR': cor_elemento,
                    })

            for pt in placemark.findall('.//Point/coordinates'):
                if not pt.text:
                    continue
                coords = extrair_coordenadas_vis(pt.text)
                if coords:
                    registros_flat.append({
                        'ALIMENTADOR': nome_arquivo,
                        'REGIONAL': regional,
                        'MUNICIPIO': municipio,
                        'TIPO_GEOMETRIA': 'Ponto',
                        'TIPO_REDE': nome_pasta,
                        'NOME': nome_elemento,
                        'COORDS': coords[0],
                        'COR': cor_elemento,
                    })

    if registros_flat:
        return pd.DataFrame(registros_flat)
    return None

def processar_e_salvar_kmz_paralelo(arquivos):
    base_map = load_base_mapping()
    geo_data = get_base_geojson()
    df_lote = []
    processados = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(processar_um_kmz, f.name, f.getvalue(), base_map, geo_data): f for f in arquivos}
        for future, arquivo in futures.items():
            try:
                df_alimentador = future.result()
            except Exception:
                df_alimentador = None
            if df_alimentador is not None and not df_alimentador.empty:
                df_alimentador['COORDS'] = df_alimentador['COORDS'].apply(json.dumps)
                df_lote.append(df_alimentador)
                processados.append(arquivo.name.upper().replace('.KMZ', '').replace('.KML', ''))

    if df_lote:
        df_final = pd.concat(df_lote, ignore_index=True)
        conn = sqlite3.connect("database/redes.db")
        c = conn.cursor()
        for alim in processados:
            c.execute("DELETE FROM malha WHERE ALIMENTADOR = ?", (alim,))
        df_final.to_sql('malha', conn, if_exists='append', index=False)
        conn.commit()
        conn.close()

    return processados

@st.cache_data(show_spinner=False)
def carregar_banco_redes():
    try:
        conn = sqlite3.connect("database/redes.db")
        df = pd.read_sql("SELECT * FROM malha", conn)
        conn.close()
        if not df.empty:
            df['COORDS'] = df['COORDS'].apply(json.loads)
        return df
    except:
        return pd.DataFrame()

@st.cache_data(show_spinner=False)
def carregar_e_cruzar_obras():
    file_path = "BASE_LEVANTAMENTO_ATUALIZADA.xlsx"
    if not os.path.exists(file_path): return "Arquivo 'BASE_LEVANTAMENTO_ATUALIZADA.xlsx' não encontrado.", None, None, None
        
    try:
        df_obras = pd.read_excel(file_path)
        status_sisco_col = next((c for c in df_obras.columns if 'STATUS SISCO' in str(c).upper()), None)
        status_list_col = next((c for c in df_obras.columns if 'STATUS LIST' in str(c).upper()), None)
        lat_col = next((c for c in df_obras.columns if 'LATITUDE' in str(c).upper() or 'LAT' == str(c).upper()), None)
        lon_col = next((c for c in df_obras.columns if 'LONGITUDE' in str(c).upper() or 'LON' == str(c).upper()), None)
        
        if not all([status_sisco_col, status_list_col, lat_col, lon_col]):
            return "Erro: Colunas obrigatórias ausentes na planilha (Status ou Coordenadas).", None, None, None
            
        mun_col = next((c for c in df_obras.columns if 'MUNICIPIO' in str(c).upper() or 'CIDADE' in str(c).upper()), None)
        if mun_col:
            df_obras['MUNICIPIO_NORM'] = df_obras[mun_col].apply(lambda x: remove_accents(str(x)).upper().strip() if pd.notnull(x) else "DESCONHECIDO")
        else:
            df_obras['MUNICIPIO_NORM'] = "DESCONHECIDO"
            
        base_map = load_base_mapping()
        df_obras['REGIONAL_NORM'] = df_obras['MUNICIPIO_NORM'].map(base_map).fillna("DESCONHECIDO")

        data_col = next((c for c in df_obras.columns if 'DATA ABERTURA' in str(c).upper()), None)
        if data_col: df_obras['DATA_DT'] = pd.to_datetime(df_obras[data_col], errors='coerce')
        else: df_obras['DATA_DT'] = pd.NaT

        if df_obras[lat_col].dtype == object: df_obras[lat_col] = df_obras[lat_col].astype(str).str.replace(',', '.')
        if df_obras[lon_col].dtype == object: df_obras[lon_col] = df_obras[lon_col].astype(str).str.replace(',', '.')
        df_obras['LAT_CLEAN'] = pd.to_numeric(df_obras[lat_col], errors='coerce')
        df_obras['LON_CLEAN'] = pd.to_numeric(df_obras[lon_col], errors='coerce')
        
        mask_valid_coords = (
            (df_obras['LAT_CLEAN'].notnull()) & (df_obras['LON_CLEAN'].notnull()) & 
            (df_obras['LAT_CLEAN'] != 0.0) & (df_obras['LON_CLEAN'] != 0.0) & 
            (df_obras['LAT_CLEAN'] >= -35.0) & (df_obras['LAT_CLEAN'] <= 5.0) & 
            (df_obras['LON_CLEAN'] >= -75.0) & (df_obras['LON_CLEAN'] <= -30.0)
        )
        df_invalidas = df_obras[~mask_valid_coords].copy()
        df_obras = df_obras[mask_valid_coords]
        
        mask_concluida = df_obras[status_sisco_col].astype(str).str.contains('CONCLU', case=False, na=False)
        df_concluidas = df_obras[mask_concluida].copy()
        
        def normalizar(x): return remove_accents(str(x)).upper().strip()
        df_obras['STATUS_LIST_NORM'] = df_obras[status_list_col].apply(normalizar)
        status_alvos = ['0', 'EM LEVANTAMENTO', 'CORRECAO DE LEVANTAMENTO']
        mask_andamento = df_obras['STATUS_LIST_NORM'].isin(status_alvos)
        df_andamento = df_obras[mask_andamento & (~mask_concluida)].copy()
        
        df_andamento['CONFLITO'], df_andamento['PROTOCOLO_CONFLITO'], df_andamento['DISTANCIA_CONFLITO'], df_andamento['NOME_CONCLUIDA'] = False, "", 0.0, ""
        
        if not df_concluidas.empty and not df_andamento.empty:
            pts_concluidas = [latlon_to_xyz(row['LAT_CLEAN'], row['LON_CLEAN']) for _, row in df_concluidas.iterrows()]
            arvore_kdtree = cKDTree(pts_concluidas)
            c_flags, c_protos, c_dists, c_nomes = [], [], [], []
            for _, row in df_andamento.iterrows():
                xyz = latlon_to_xyz(row['LAT_CLEAN'], row['LON_CLEAN'])
                _, idx_mais_proximo = arvore_kdtree.query(xyz)
                obra_concluida_proxima = df_concluidas.iloc[idx_mais_proximo]
                distancia_exata_m = haversine(row['LAT_CLEAN'], row['LON_CLEAN'], obra_concluida_proxima['LAT_CLEAN'], obra_concluida_proxima['LON_CLEAN']) * 1000
                if distancia_exata_m <= 50:
                    c_flags.append(True); c_protos.append(str(obra_concluida_proxima.get('PROTOCOLO', 'S/N')))
                    c_dists.append(distancia_exata_m); c_nomes.append(str(obra_concluida_proxima.get('NOME', 'S/N')))
                else:
                    c_flags.append(False); c_protos.append(""); c_dists.append(0.0); c_nomes.append("")
            df_andamento['CONFLITO'], df_andamento['PROTOCOLO_CONFLITO'], df_andamento['DISTANCIA_CONFLITO'], df_andamento['NOME_CONCLUIDA'] = c_flags, c_protos, c_dists, c_nomes
            
        return "OK", df_concluidas, df_andamento, df_invalidas
    except Exception as e: return f"Erro processando dados: {str(e)}", None, None, None

@st.cache_data(ttl=300)
def obter_radar_chuva_url():
    try:
        req = requests.get("https://api.rainviewer.com/public/weather-maps.json", timeout=5)
        data = req.json()
        host = data.get('host', 'https://tilecache.rainviewer.com')
        path_chuva = data['radar']['past'][-1]['path']
        url_chuva = f"{host}{path_chuva}/256/{{z}}/{{x}}/{{y}}/2/1_1.png"
        path_nuvem = None
        if 'satellite' in data and 'infrared' in data['satellite']:
            path_nuvem = data['satellite']['infrared'][-1]['path']
            url_nuvem = f"{host}{path_nuvem}/256/{{z}}/{{x}}/{{y}}/0/1_1.png"
        return url_chuva, url_nuvem
    except:
        return None, None

# ==========================================
# 2. ESTRUTURA DA TELA E CONTAINERS
# ==========================================
st.markdown("<h2 style='color: #0D256C;'>🗺️ Gestão de Malha Elétrica e Obras (Inteligência Geográfica)</h2>", unsafe_allow_html=True)

kpi_container = st.empty()
map_container = st.empty()
table_container = st.container()

df = carregar_banco_redes()
base_map = load_base_mapping()
geo_data_ibge = get_base_geojson()

# ==========================================
# PREPARAÇÃO DAS ÁREAS ESPECIAIS (BOUNDING BOX OTIMIZADO)
# ==========================================
def preprocessar_bboxes_kml(geo_data):
    if not geo_data: return
    for feat in geo_data['features']:
        geom = feat['geometry']
        if geom['type'] == 'Polygon':
            bboxes = []
            for ring in geom['coordinates']:
                lons = [pt[0] for pt in ring]
                lats = [pt[1] for pt in ring]
                bboxes.append((min(lons), max(lons), min(lats), max(lats)))
            feat['bboxes'] = bboxes

# As áreas especiais são pesadas. Não lemos os seis KMLs no arranque do app.
# Cada arquivo só é aberto quando sua caixa for marcada na barra lateral.
geo_q = geo_i = geo_a = None
geo_uc_fed = geo_uc_est = geo_uc_mun = None
dict_areas_especiais = {}

def verificar_areas_da_obra(lat, lon):
    encontradas = []
    for categoria, geo_data in dict_areas_especiais.items():
        if not geo_data: continue
        for feat in geo_data['features']:
            geom = feat['geometry']
            nome = feat['properties'].get('NOME', 'Sem Nome')
            if geom['type'] == 'Polygon':
                for i, ring in enumerate(geom['coordinates']):
                    min_lon, max_lon, min_lat, max_lat = feat['bboxes'][i]
                    if (min_lon <= lon <= max_lon) and (min_lat <= lat <= max_lat):
                        if is_point_in_polygon(lon, lat, ring):
                            encontradas.append(f"<b>{categoria}:</b> {nome}")
                            break
            elif geom['type'] == 'Point':
                pt_lon, pt_lat = geom['coordinates']
                if haversine(lat, lon, pt_lat, pt_lon) * 1000 <= 150:
                    encontradas.append(f"<b>{categoria}:</b> {nome} (Raio 150m)")
    return "<br>".join(encontradas) if encontradas else "Nenhuma restrição"

# ==========================================
# 3. INTERFACE E SINCRONIZAÇÃO VIA GITHUB
# ==========================================
with st.sidebar:
    with st.expander("📥 1. Banco de Dados e Sincronização", expanded=True):
        st.markdown("A ferramenta lê as redes automaticamente da pasta **`kmzs`** no repositório.")
        
        # Garante que a pasta kmzs exista
        pasta_kmz = "kmzs"
        if not os.path.exists(pasta_kmz):
            os.makedirs(pasta_kmz, exist_ok=True)
            
        # Lista os arquivos disponíveis no GitHub localmente
        arquivos_repositorio = [f for f in os.listdir(pasta_kmz) if f.lower().endswith(('.kmz', '.kml'))]
        
        # Detecta KMZ novos OU alterados pelo conteúdo, mesmo quando o nome não mudou.
        assinaturas_db = carregar_assinaturas_kmz()
        arquivos_pendentes = []
        for f in arquivos_repositorio:
            caminho = os.path.join(pasta_kmz, f)
            nome_alim = f.upper().replace('.KMZ', '').replace('.KML', '')
            try:
                stat = os.stat(caminho)
                anterior = assinaturas_db.get(nome_alim)
                if not anterior:
                    # Arquivo ainda não possui assinatura na nova versão. Não fazemos hash
                    # na abertura do app: ele só será lido quando o usuário sincronizar.
                    arquivos_pendentes.append(f)
                elif anterior.get('tamanho') == stat.st_size and anterior.get('mtime_ns') == stat.st_mtime_ns:
                    continue
                else:
                    sha_atual = assinatura_arquivo_kmz(caminho, stat.st_size, stat.st_mtime_ns)
                    if anterior.get('hash') != sha_atual:
                        arquivos_pendentes.append(f)
            except Exception:
                arquivos_pendentes.append(f)

        if arquivos_pendentes:
            st.info(f"📂 {len(arquivos_pendentes)} arquivo(s) novo(s) ou alterado(s) aguardando processamento.")
            if st.button(f"🚀 Sincronizar {len(arquivos_pendentes)} Redes", type="primary", use_container_width=True):
                class LocalFileAdapter:
                    def __init__(self, filepath):
                        self.name = os.path.basename(filepath)
                        self.filepath = filepath
                    def getvalue(self):
                        with open(self.filepath, 'rb') as f:
                            return f.read()

                lista_adapters = [LocalFileAdapter(os.path.join(pasta_kmz, f)) for f in arquivos_pendentes]
                caminhos_por_alim = {a.name.upper().replace('.KMZ', '').replace('.KML', ''): a.filepath for a in lista_adapters}
                processados_total = []
                tamanho_lote = 15
                total_lotes = math.ceil(len(lista_adapters) / tamanho_lote)
                barra_progresso = st.progress(0.0)
                texto_status = st.empty()

                for i in range(0, len(lista_adapters), tamanho_lote):
                    lote_atual = (i // tamanho_lote) + 1
                    lote_arquivos = lista_adapters[i:i+tamanho_lote]
                    texto_status.text(f"⏳ Processando e salvando lote {lote_atual} de {total_lotes}...")
                    processados = processar_e_salvar_kmz_paralelo(lote_arquivos)
                    processados_total.extend(processados)
                    for alim in processados:
                        caminho_ok = caminhos_por_alim.get(alim)
                        if caminho_ok:
                            registrar_assinatura_kmz(caminho_ok)
                    barra_progresso.progress(lote_atual / total_lotes)
                    gc.collect()

                if processados_total:
                    st.success(f"✅ Sincronização finalizada! {len(processados_total)} rede(s) atualizada(s).")
                    carregar_banco_redes.clear()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Nenhum KMZ pôde ser processado. Os arquivos originais não foram modificados.")
        else:
            st.success(f"✅ O banco de dados está atualizado com os arquivos da pasta `{pasta_kmz}`.")
    with st.expander("🔎 2. Pesquisas Inteligentes", expanded=False):
        tab_nome, tab_coord = st.tabs(["📝 Por Nome/ID", "📍 Por Coordenada"])
        termo_pesquisa, busca_lat, busca_lon = "", None, None
        with tab_nome: termo_pesquisa = st.text_input("Nome/Num. Poste ou Trafo:", placeholder="Ex: 554930...").strip().upper()
        with tab_coord:
            c_lat, c_lon = st.columns(2)
            with c_lat: lat_input = st.text_input("Latitude:", placeholder="Ex: -5.532")
            with c_lon: lon_input = st.text_input("Longitude:", placeholder="Ex: -47.432")
            if lat_input and lon_input:
                try:
                    b_lat, b_lon = float(lat_input.replace(',', '.').strip()), float(lon_input.replace(',', '.').strip())
                    if -35.0 <= b_lat <= 5.0 and -75.0 <= b_lon <= -30.0: busca_lat, busca_lon = b_lat, b_lon
                    else: st.warning("⚠️ Coordenada fora do Brasil.")
                except: st.warning("⚠️ Formato inválido.")

    with st.expander("🔍 3. Filtros Geográficos", expanded=True):
        lista_regioes = sorted(list(set(base_map.values()))) if base_map else ["CENTRO", "LESTE", "NOROESTE", "NORTE", "SUL"]
        regioes_sel = st.multiselect("📍 Regional:", lista_regioes)
        
        lista_municipios = []
        for mun, reg in base_map.items():
            if not regioes_sel or reg in regioes_sel: lista_municipios.append(mun)
        municipios_sel = st.multiselect("🏙️ Município (Foco e Contorno):", sorted(lista_municipios))
        
        df_filt = df.copy()
        if not df.empty:
            if regioes_sel: df_filt = df_filt[df_filt['REGIONAL'].isin(regioes_sel)]
            if municipios_sel: df_filt = df_filt[df_filt['MUNICIPIO'].isin(municipios_sel)]
        
        lista_alimentadores = sorted(df_filt['ALIMENTADOR'].unique().tolist()) if not df_filt.empty else []
        alim_sel = st.multiselect("⚡ Alimentadores visíveis:", lista_alimentadores)
        alimentador_foco = st.selectbox(
            "🎯 Localizar alimentador no mapa:",
            ["Todos / visão geral"] + lista_alimentadores,
            help="Ao escolher um alimentador, o mapa enquadra automaticamente todo o KMZ correspondente e libera suas camadas detalhadas.",
        )

        if alimentador_foco != "Todos / visão geral":
            alimentadores_visiveis = [alimentador_foco]
        elif alim_sel:
            alimentadores_visiveis = alim_sel
        else:
            alimentadores_visiveis = lista_alimentadores

        detalhe_por_selecao = alimentador_foco != "Todos / visão geral" or (0 < len(alim_sel) <= MAX_ALIMENTADORES_DETALHE)
        if len(alim_sel) > MAX_ALIMENTADORES_DETALHE and alimentador_foco == "Todos / visão geral":
            st.caption(
                f"⚡ Para manter o mapa fluido, até {MAX_ALIMENTADORES_DETALHE} alimentadores são carregados em detalhe. "
                "Com mais alimentadores selecionados, o mapa usa somente as redes Primária/Secundária simplificadas."
            )

    camadas_ativas = {}
    tipos_kmz_disponiveis = []
    if not df.empty and alimentadores_visiveis:
        with st.expander("🗂️ 4. Camadas dos KMZ", expanded=False):
            st.markdown(
                "Os filtros ficam no **rodapé do mapa**. Na visão geral são enviados apenas os traçados Primário/Secundário simplificados. "
                "Ao selecionar um alimentador, Poste, Transformador e os demais equipamentos ficam disponíveis sem recarregar a página a cada zoom."
            )
            tipos_kmz_disponiveis = sorted({normalizar_tipo_rede(v) for v in df_filt['TIPO_REDE'].dropna().tolist()}) if not df_filt.empty else []
            if tipos_kmz_disponiveis:
                st.caption("Divisões encontradas: " + ", ".join(ROTULOS_REDE.get(t, t.title()) for t in tipos_kmz_disponiveis))
            camadas_ativas = {alim: tipos_kmz_disponiveis for alim in alimentadores_visiveis}

            if alimentador_foco != "Todos / visão geral":
                tipos_foco = {normalizar_tipo_rede(v) for v in df.loc[df['ALIMENTADOR'] == alimentador_foco, 'TIPO_REDE'].dropna().tolist()}
                faltantes = sorted(TIPOS_ESPERADOS_KMZ - tipos_foco)
                if faltantes:
                    st.warning("Divisões não encontradas neste KMZ: " + ", ".join(ROTULOS_REDE.get(t, t.title()) for t in faltantes))
                else:
                    st.success("Todas as divisões padrão do KMZ foram encontradas.")

    with st.expander("🗺️ 5. Áreas Especiais", expanded=False):
        mostrar_quilombos = st.checkbox("🟠 Áreas Quilombolas", value=False)
        mostrar_indigenas = st.checkbox("🟢 Terras Indígenas", value=False)
        mostrar_arqueologia = st.checkbox("🟤 Sítios Arqueológicos", value=False)
        mostrar_uc_federal = st.checkbox("🟡 UC Federal", value=False)
        mostrar_uc_estadual = st.checkbox("🟡 UC Estadual", value=False)
        mostrar_uc_municipal = st.checkbox("🟡 UC Municipal", value=False)

    geo_q = get_kml_cached("kmls/Áreas Quilombolas.kml", "#ff7f00") if mostrar_quilombos else None
    geo_i = get_kml_cached("kmls/Terras Indigenas.kml", "#2ca02c") if mostrar_indigenas else None
    geo_a = get_kml_cached("kmls/Sítios Arqueológicos.kml", "#8c564b") if mostrar_arqueologia else None
    geo_uc_fed = get_kml_cached("kmls/UC Federal.kml", "#e6b800") if mostrar_uc_federal else None
    geo_uc_est = get_kml_cached("kmls/UC Estadual.kml", "#ffff00") if mostrar_uc_estadual else None
    geo_uc_mun = get_kml_cached("kmls/UC Municipal.kml", "#ffff00") if mostrar_uc_municipal else None
    for _geo in (geo_q, geo_i, geo_a, geo_uc_fed, geo_uc_est, geo_uc_mun):
        preprocessar_bboxes_kml(_geo)
    dict_areas_especiais = {
        "Quilombo": geo_q, "Terra Indígena": geo_i, "Sítio Arqueológico": geo_a,
        "UC Federal": geo_uc_fed, "UC Estadual": geo_uc_est, "UC Municipal": geo_uc_mun
    }

    with st.expander("🚧 6. Obras e Projetos", expanded=True):
        mostrar_todas_obras = st.checkbox("📍 TODAS AS OBRAS (Clusters)", value=False)
        mostrar_concluidas = st.checkbox("🔵 OBRAS CONCLUÍDAS", value=False)
        mostrar_conflitantes = st.checkbox("🚨 OBRAS CONFLITANTES (Raio 50m)", value=False)
        mostrar_heatmap = st.checkbox("🔥 Mapa de Calor (Densidade de Obras)", value=False)
        mostrar_clima = st.checkbox("🌦️ Radar Climático (Nuvens e Chuva)", value=False)
        mostrar_streetview = st.checkbox("🛣️ Cobertura Street View", value=False)

        msg_obras, df_concluidas, df_andamento, df_invalidas = "OK", None, None, None
        if mostrar_concluidas or mostrar_conflitantes or mostrar_heatmap or mostrar_todas_obras:
            msg_obras, df_concluidas, df_andamento, df_invalidas = carregar_e_cruzar_obras()
            if msg_obras != "OK":
                st.sidebar.warning(f"⚠️ {msg_obras}")
            else:
                if regioes_sel:
                    if df_concluidas is not None and not df_concluidas.empty: df_concluidas = df_concluidas[df_concluidas['REGIONAL_NORM'].isin(regioes_sel)]
                    if df_andamento is not None and not df_andamento.empty: df_andamento = df_andamento[df_andamento['REGIONAL_NORM'].isin(regioes_sel)]
                    if df_invalidas is not None and not df_invalidas.empty: df_invalidas = df_invalidas[df_invalidas['REGIONAL_NORM'].isin(regioes_sel)]
                if municipios_sel:
                    if df_concluidas is not None and not df_concluidas.empty: df_concluidas = df_concluidas[df_concluidas['MUNICIPIO_NORM'].isin(municipios_sel)]
                    if df_andamento is not None and not df_andamento.empty: df_andamento = df_andamento[df_andamento['MUNICIPIO_NORM'].isin(municipios_sel)]
                    if df_invalidas is not None and not df_invalidas.empty: df_invalidas = df_invalidas[df_invalidas['MUNICIPIO_NORM'].isin(municipios_sel)]

                val_mins, val_maxs = [], []
                if df_concluidas is not None and not df_concluidas.empty:
                    val_mins.append(df_concluidas['DATA_DT'].min()); val_maxs.append(df_concluidas['DATA_DT'].max())
                if df_andamento is not None and not df_andamento.empty:
                    val_mins.append(df_andamento['DATA_DT'].min()); val_maxs.append(df_andamento['DATA_DT'].max())
                val_mins = [d for d in val_mins if pd.notnull(d)]
                val_maxs = [d for d in val_maxs if pd.notnull(d)]

                if val_mins and val_maxs:
                    st.markdown("<br>", unsafe_allow_html=True)
                    min_dt, max_dt = min(val_mins).date(), max(val_maxs).date()
                    if min_dt != max_dt:
                        data_filtro = st.slider("🕒 Linha do Tempo (Data de Abertura):", min_value=min_dt, max_value=max_dt, value=(min_dt, max_dt), format="DD/MM/YY")
                        if df_concluidas is not None and not df_concluidas.empty:
                            mask_c = (df_concluidas['DATA_DT'].dt.date >= data_filtro[0]) & (df_concluidas['DATA_DT'].dt.date <= data_filtro[1])
                            df_concluidas = df_concluidas[mask_c | df_concluidas['DATA_DT'].isnull()]
                        if df_andamento is not None and not df_andamento.empty:
                            mask_a = (df_andamento['DATA_DT'].dt.date >= data_filtro[0]) & (df_andamento['DATA_DT'].dt.date <= data_filtro[1])
                            df_andamento = df_andamento[mask_a | df_andamento['DATA_DT'].isnull()]

                qtd_conflitos = df_andamento['CONFLITO'].sum() if df_andamento is not None else 0

    with st.expander("🗑️ 7. Gerenciar Malha Local", expanded=False):
        alim_para_deletar = st.selectbox("Apagar Alimentador do Banco:", ["Selecione..."] + sorted(df['ALIMENTADOR'].unique().tolist()) if not df.empty else ["Selecione..."])
        if alim_para_deletar != "Selecione...":
            if st.button("❌ Excluir Permanentemente", use_container_width=True):
                conn = sqlite3.connect("database/redes.db")
                c = conn.cursor()
                c.execute("DELETE FROM malha WHERE ALIMENTADOR = ?", (alim_para_deletar,))
                c.execute("DELETE FROM arquivos_kmz WHERE ALIMENTADOR = ?", (alim_para_deletar,))
                conn.commit()
                conn.close()
                carregar_banco_redes.clear()
                st.success("Excluído do Banco de Dados!")
                time.sleep(1)
                st.rerun()

# ==========================================
# DASHBOARD DE INDICADORES E GRÁFICOS
# ==========================================
def render_kpi(icone, titulo, valor, cor_borda):
    return f"""
    <div style="background-color: white; border-radius: 8px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 6px solid {cor_borda}; text-align: left; height: 100%;">
        <p style="margin: 0; font-size: 14px; color: #666; font-weight: 600;">{icone} {titulo}</p>
        <p style="margin: 0; font-size: 32px; color: #222; font-weight: 800; padding-top: 5px;">{valor}</p>
    </div>
    """

with kpi_container.container():
    c1, c2, c3, c4 = st.columns(4)
    val_alim = len(df['ALIMENTADOR'].unique()) if not df.empty else 0
    val_conc = len(df_concluidas) if df_concluidas is not None else 0
    val_anda = len(df_andamento) if df_andamento is not None else 0
    val_conf = df_andamento['CONFLITO'].sum() if df_andamento is not None else 0
    
    c1.markdown(render_kpi("⚡", "ALIMENTADORES MAPEADOS", val_alim, "#808080"), unsafe_allow_html=True)
    c2.markdown(render_kpi("🔵", "OBRAS CONCLUÍDAS", val_conc, "#1f77b4"), unsafe_allow_html=True)
    c3.markdown(render_kpi("🟢", "OBRAS EM ANDAMENTO", val_anda, "#2ca02c"), unsafe_allow_html=True)
    c4.markdown(render_kpi("🚨", "CONFLITOS (50m)", val_conf, "#d62728"), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if msg_obras == "OK" and val_conf > 0:
        df_conf = df_andamento[df_andamento['CONFLITO']]
        if not df_conf.empty:
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                df_barras = df_conf['MUNICIPIO_NORM'].value_counts().reset_index()
                fig1 = px.bar(df_barras, x='MUNICIPIO_NORM', y='count', title="📍 Cidades com Mais Conflitos", color_discrete_sequence=['#d62728'], text='count')
                fig1.update_traces(textposition='outside')
                fig1.update_layout(xaxis_title="", yaxis_title="Qtd de Obras em Conflito")
                st.plotly_chart(fig1, use_container_width=True)
            with col_chart2:
                fig2 = px.pie(df_conf, names='STATUS LIST', title="📊 Status das Obras Sobrepostas", hole=0.4, color_discrete_sequence=['#ff7f0e', '#ffbb78', '#d62728'])
                fig2.update_traces(textposition='outside', textinfo='value+percent')
                st.plotly_chart(fig2, use_container_width=True)

# ==========================================
# 4. CONSTRUÇÃO DO MAPA FOLIUM (BASE E DARK MODE)
# ==========================================
mapa = folium.Map(
    location=[MAPA_CENTRO_INICIAL[0], MAPA_CENTRO_INICIAL[1]],
    zoom_start=6,
    tiles=None,
    prefer_canvas=True,
    zoom_control=True,
    control_scale=True,
)

mapa.add_child(MeasureControl(position='topleft', primary_length_unit='meters', primary_area_unit='sqmeters'))
Draw(export=False, position='topleft').add_to(mapa)

# 🇧🇷 TRADUÇÃO DOS CONTROLES DE DESENHO (DRAW) PARA PORTUGUÊS (PT-BR)
js_draw_loc = """
<script>
    setTimeout(function() {
        if (typeof L !== 'undefined' && L.drawLocal) {
            L.drawLocal.draw.toolbar.actions.title = 'Cancelar desenho';
            L.drawLocal.draw.toolbar.actions.text = 'Cancelar';
            L.drawLocal.draw.toolbar.finish.title = 'Finalizar desenho';
            L.drawLocal.draw.toolbar.finish.text = 'Finalizar';
            L.drawLocal.draw.toolbar.undo.title = 'Desfazer último ponto';
            L.drawLocal.draw.toolbar.undo.text = 'Desfazer';
            L.drawLocal.draw.toolbar.buttons.polygon = 'Desenhar um polígono';
            L.drawLocal.draw.toolbar.buttons.polyline = 'Desenhar uma linha';
            L.drawLocal.draw.toolbar.buttons.rectangle = 'Desenhar um retângulo';
            L.drawLocal.draw.toolbar.buttons.circle = 'Desenhar um círculo';
            L.drawLocal.draw.toolbar.buttons.marker = 'Adicionar um marcador';
            L.drawLocal.draw.toolbar.buttons.circlemarker = 'Adicionar marcador circular';
            
            L.drawLocal.edit.toolbar.actions.save.title = 'Salvar alterações';
            L.drawLocal.edit.toolbar.actions.save.text = 'Salvar';
            L.drawLocal.edit.toolbar.actions.cancel.title = 'Cancelar edição';
            L.drawLocal.edit.toolbar.actions.cancel.text = 'Cancelar';
            L.drawLocal.edit.toolbar.actions.clearAll.title = 'Apagar todos os desenhos';
            L.drawLocal.edit.toolbar.actions.clearAll.text = 'Apagar Tudo';
        }
    }, 500);
</script>
"""
mapa.get_root().html.add_child(folium.Element(js_draw_loc))

# Camadas base. O OpenStreetMap fica ativo por padrão porque é leve e confiável.
# Satélite e mapa escuro continuam disponíveis no seletor, mas não atrasam a abertura inicial.
folium.TileLayer(
    tiles='OpenStreetMap',
    name='Mapa Base (Limpo)',
    overlay=False,
    control=True,
    show=True,
    max_zoom=20
).add_to(mapa)
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
    attr='Google',
    name='Satélite (Google Maps)',
    overlay=False,
    control=True,
    show=False,
    max_zoom=20
).add_to(mapa)
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attr='Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
    name='Mapa Base (Escuro - Foco em Redes)',
    overlay=False,
    control=True,
    show=False,
    max_zoom=20
).add_to(mapa)

if geo_data_ibge:
    def style_function(feature):
        reg_mun = feature['properties'].get('MUNICIPIO', '')
        reg_name = feature['properties'].get('REGIONAL', '')
        cor_regiao = feature['properties']['fillColor']
        if municipios_sel:
            if reg_mun in municipios_sel:
                return {'fillColor': cor_regiao, 'color': '#FF00FF', 'weight': 4, 'fillOpacity': 0.22}
            return {'fillColor': 'transparent', 'color': 'transparent', 'weight': 0, 'fillOpacity': 0}
        elif regioes_sel:
            if reg_name in regioes_sel:
                return {'fillColor': cor_regiao, 'color': cor_regiao, 'weight': 1.5, 'fillOpacity': 0.42}
            return {'fillColor': 'transparent', 'color': 'transparent', 'weight': 0, 'fillOpacity': 0}
        if reg_name == 'DESCONHECIDO':
            return {'fillColor': 'transparent', 'color': '#9ca3af', 'weight': 0.6, 'fillOpacity': 0}
        # Mantém as cores originais das regionais já na abertura do mapa.
        return {'fillColor': cor_regiao, 'color': cor_regiao, 'weight': 1.0, 'fillOpacity': 0.32}

    folium.GeoJson(geo_data_ibge, name="Divisão IBGE (Maranhão)", style_function=style_function, tooltip=folium.features.GeoJsonTooltip(fields=['name', 'REGIONAL'], aliases=['Município:', 'Regional:'], style="background-color: white; color: #333; font-family: arial; font-size: 12px; padding: 10px;"), zoom_on_click=False, show=True).add_to(mapa)

    # A divisão regional permanece visível; não removemos a camada por zoom.

todas_lats, todas_lons = [], []
busca_lats, busca_lons = [], []


# A rede detalhada não é transformada em milhares de objetos Leaflet no início.
# Cada GeoJSON é criado no navegador apenas quando filtro + zoom exigirem a camada.
kmz_payloads = {}
tipos_presentes_rodape = []
tipos_carregados_rodape = set()
tree_grid = None
grid_info = []
df_busca = pd.DataFrame()
df_base_rede = pd.DataFrame()
modo_detalhe = False

if not df.empty:
    df_base_rede = df.copy()
    if regioes_sel:
        df_base_rede = df_base_rede[df_base_rede['REGIONAL'].isin(regioes_sel)]
    if municipios_sel:
        df_base_rede = df_base_rede[df_base_rede['MUNICIPIO'].isin(municipios_sel)]
    if alimentadores_visiveis:
        df_base_rede = df_base_rede[df_base_rede['ALIMENTADOR'].isin(alimentadores_visiveis)]

    df_base_rede = df_base_rede.copy()
    if not df_base_rede.empty:
        df_base_rede['TIPO_REDE_CANON'] = df_base_rede['TIPO_REDE'].apply(normalizar_tipo_rede)
        tipos_presentes_rodape = sorted(df_base_rede['TIPO_REDE_CANON'].dropna().unique().tolist())

    modo_detalhe = detalhe_por_selecao and not df_base_rede.empty

    if busca_lat is not None and busca_lon is not None and not df_base_rede.empty:
        pts, indices = [], []
        for idx, row in df_base_rede.iterrows():
            if row['TIPO_GEOMETRIA'] == 'Ponto':
                pts.append(latlon_to_xyz(row['COORDS'][0], row['COORDS'][1])); indices.append(idx)
            else:
                coords_busca = row['COORDS']
                passo = max(1, len(coords_busca) // 250)
                for pt in coords_busca[::passo]:
                    pts.append(latlon_to_xyz(pt[0], pt[1])); indices.append(idx)
        if pts:
            tree_busca = cKDTree(pts)
            _, min_idx_in_pts = tree_busca.query(latlon_to_xyz(busca_lat, busca_lon))
            nearest_idx = indices[min_idx_in_pts]
            elem_prox = df_base_rede.loc[nearest_idx]
            if elem_prox['TIPO_GEOMETRIA'] == 'Ponto':
                dist_metros = haversine(busca_lat, busca_lon, elem_prox['COORDS'][0], elem_prox['COORDS'][1]) * 1000
            else:
                dist_metros = min(haversine(busca_lat, busca_lon, p[0], p[1]) for p in elem_prox['COORDS']) * 1000
            st.sidebar.success(f"🎯 **Alvo mais próximo:** {elem_prox['TIPO_REDE_CANON']} ({elem_prox['NOME']}) a {dist_metros:.1f} metros.")
            df_busca = df_base_rede.loc[[nearest_idx]].copy()
    elif termo_pesquisa != "" and not df_base_rede.empty:
        mask_nome = df_base_rede['NOME'].astype(str).str.contains(termo_pesquisa, case=False, na=False)
        df_busca = df_base_rede[mask_nome].copy()

    if not df_base_rede.empty:
        if modo_detalhe:
            df_render = df_base_rede.copy()
            tolerancia_linha = 0.00010
        else:
            df_render = df_base_rede[
                (df_base_rede['TIPO_GEOMETRIA'] == 'Linha') &
                (df_base_rede['TIPO_REDE_CANON'].isin({'REDE PRIMARIA', 'REDE SECUNDARIA'}))
            ].copy()
            tolerancia_linha = 0.00120
            if not df_render.empty:
                st.sidebar.caption("⚡ Visão geral leve: apenas Primária/Secundária simplificadas. Selecione um alimentador para liberar detalhes.")

        tipos_carregados_rodape = set(df_render['TIPO_REDE_CANON'].dropna().unique().tolist())

        precisa_indice_rede = bool(mostrar_todas_obras or mostrar_concluidas or mostrar_conflitantes)
        if precisa_indice_rede:
            grid_pts, grid_info = [], []
            for _, row in df_render.iterrows():
                if row['TIPO_GEOMETRIA'] == 'Ponto':
                    lat0, lon0 = row['COORDS'][0], row['COORDS'][1]
                    grid_pts.append(latlon_to_xyz(lat0, lon0))
                    grid_info.append((row['TIPO_REDE_CANON'], row['NOME'], lat0, lon0))
                else:
                    coords_idx = row['COORDS']
                    passo = max(1, len(coords_idx) // 200)
                    for pt in coords_idx[::passo]:
                        grid_pts.append(latlon_to_xyz(pt[0], pt[1]))
                        grid_info.append((row['TIPO_REDE_CANON'], row['NOME'], pt[0], pt[1]))
            tree_grid = cKDTree(grid_pts) if grid_pts else None

        if not modo_detalhe:
            # Na visão geral, cada categoria vira um único MultiLineString. Isso evita
            # milhares de objetos e popups desnecessários antes de escolher um alimentador.
            linhas_por_tipo = {tipo: [] for tipo in tipos_presentes_rodape}
            for _, row in df_render.iterrows():
                tipo = row['TIPO_REDE_CANON']
                coords_linha = simplificar_linha(row['COORDS'], tolerancia_linha)
                if len(coords_linha) >= 2:
                    linhas_por_tipo.setdefault(tipo, []).append([[float(p[1]), float(p[0])] for p in coords_linha])
            for tipo, linhas in linhas_por_tipo.items():
                if not linhas:
                    continue
                kmz_payloads[tipo] = {
                    "type": "FeatureCollection",
                    "features": [{
                        "type": "Feature",
                        "geometry": {"type": "MultiLineString", "coordinates": linhas},
                        "properties": {
                            "TIPO_REDE": ROTULOS_REDE.get(tipo, tipo.title()),
                            "NOME": "Visão geral",
                            "ALIMENTADOR": "Múltiplos alimentadores",
                            "MUNICIPIO": "Visão geral do mapa",
                            "GPS": "Aproxime ou selecione um alimentador para detalhes",
                        },
                    }],
                }
        else:
            features_por_tipo = {tipo: [] for tipo in tipos_presentes_rodape}
            for _, row in df_render.iterrows():
                tipo = row['TIPO_REDE_CANON']
                if tipo not in features_por_tipo:
                    features_por_tipo[tipo] = []

                if row['TIPO_GEOMETRIA'] == 'Ponto':
                    coords = row['COORDS']
                    lat0, lon0 = float(coords[0]), float(coords[1])
                    geom = {"type": "Point", "coordinates": [lon0, lat0]}
                    gps = f"{lat0:.5f}, {lon0:.5f}"
                else:
                    coords_linha = row['COORDS']
                    if len(coords_linha) > 2500:
                        coords_linha = simplificar_linha(coords_linha, tolerancia_linha)
                    geom = {"type": "LineString", "coordinates": [[float(p[1]), float(p[0])] for p in coords_linha]}
                    gps = "Linha de Múltiplos Pontos"

                features_por_tipo[tipo].append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "TIPO_REDE": ROTULOS_REDE.get(tipo, tipo.title()),
                        "NOME": str(row['NOME']),
                        "ALIMENTADOR": str(row['ALIMENTADOR']),
                        "MUNICIPIO": f"{row['MUNICIPIO']} - {row['REGIONAL']}",
                        "GPS": gps,
                    },
                })

            for tipo, features in features_por_tipo.items():
                if features:
                    kmz_payloads[tipo] = {"type": "FeatureCollection", "features": features}

    if not df_busca.empty or (busca_lat is not None and busca_lon is not None):
        fg_busca = folium.FeatureGroup(name="Resultado da Pesquisa", show=True)
        for _, row in df_busca.iterrows():
            if row['TIPO_GEOMETRIA'] == 'Ponto':
                sv_lat, sv_lon = row['COORDS'][0], row['COORDS'][1]
            else:
                sv_lat, sv_lon = row['COORDS'][0][0], row['COORDS'][0][1]
            sv_url = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={sv_lat},{sv_lon}"
            html_popup = f"<div style='min-width:250px;font-family:sans-serif'><h4 style='margin-top:0;color:#FF00FF'>{row['TIPO_REDE_CANON']}</h4><b>IDENTIFICAÇÃO:</b> {html.escape(str(row['NOME']))}<br><b>LOCAL:</b> {html.escape(str(row['MUNICIPIO']))}<br><a href='{sv_url}' target='_blank'>👁️ Abrir Street View</a></div>"
            popup = folium.Popup(html_popup, max_width=350)
            if row['TIPO_GEOMETRIA'] == 'Linha':
                folium.PolyLine(locations=row['COORDS'], color='#FF00FF', weight=8, opacity=1.0, popup=popup, tooltip=f"ALVO ENCONTRADO: {html.escape(str(row['NOME']))}").add_to(fg_busca)
                for pt in row['COORDS']:
                    busca_lats.append(pt[0]); busca_lons.append(pt[1])
            else:
                folium.Marker(location=row['COORDS'], icon=folium.Icon(color='purple', icon='star'), popup=popup, tooltip=f"ALVO ENCONTRADO: {html.escape(str(row['NOME']))}").add_to(fg_busca)
                busca_lats.append(row['COORDS'][0]); busca_lons.append(row['COORDS'][1])
        if busca_lat is not None and busca_lon is not None:
            folium.Marker(location=[busca_lat, busca_lon], icon=folium.Icon(color='orange', icon='map-pin', prefix='fa'), tooltip="Sua Pesquisa GPS").add_to(fg_busca)
        fg_busca.add_to(mapa)

def calcular_rede_proxima(lat, lon):
    if not tree_grid: return "<span style='color:gray'>Ative um alimentador no filtro para calcular</span>"
    xyz = latlon_to_xyz(lat, lon)
    _, idx = tree_grid.query(xyz)
    tipo, nome, g_lat, g_lon = grid_info[idx]
    dist_m = haversine(lat, lon, g_lat, g_lon) * 1000
    return f"<b>{tipo}</b> {nome} ({dist_m:.1f}m)"

# ==========================================
# RENDERIZAÇÃO DAS ÁREAS ESPECIAIS (COM POPUPS)
# ==========================================
def adicionar_camada_area(geo_data, nome_camada, mapa_obj, cor, is_ponto=False):
    if geo_data:
        estilo = lambda x: {'fillColor': cor, 'color': cor, 'weight': 2, 'fillOpacity': 0.4}
        marcador = folium.CircleMarker(radius=6, fill=True, fillOpacity=1, color=cor) if is_ponto else None
        
        folium.GeoJson(
            geo_data, 
            name=nome_camada, 
            style_function=estilo if not is_ponto else None,
            marker=marcador,
            tooltip=folium.features.GeoJsonTooltip(fields=['NOME'], aliases=['Área Específica:']),
            popup=folium.features.GeoJsonPopup(fields=['NOME'], aliases=['Nome do Local:'], style="font-family: sans-serif; font-size: 14px; min-width: 200px;")
        ).add_to(mapa_obj)

if mostrar_quilombos: adicionar_camada_area(geo_q, "Áreas Quilombolas", mapa, "#ff7f00")
if mostrar_indigenas: adicionar_camada_area(geo_i, "Terras Indígenas", mapa, "#2ca02c")
if mostrar_arqueologia: adicionar_camada_area(geo_a, "Sítios Arqueológicos", mapa, "#8c564b", is_ponto=True)
if mostrar_uc_federal: adicionar_camada_area(geo_uc_fed, "UC Federal", mapa, "#e6b800")
if mostrar_uc_estadual: adicionar_camada_area(geo_uc_est, "UC Estadual", mapa, "#ffff00")
if mostrar_uc_municipal: adicionar_camada_area(geo_uc_mun, "UC Municipal", mapa, "#ffff00")


# ==========================================
# CAMADAS DE OBRAS E CRUZAMENTOS COM ÁREAS
# ==========================================
dados_tabela_conflito = []

if (mostrar_concluidas or mostrar_conflitantes or mostrar_heatmap or mostrar_todas_obras) and msg_obras == "OK":
    
    if mostrar_heatmap:
        heat_data = []
        if df_andamento is not None and not df_andamento.empty: heat_data.extend(df_andamento[['LAT_CLEAN', 'LON_CLEAN']].values.tolist())
        if df_concluidas is not None and not df_concluidas.empty: heat_data.extend(df_concluidas[['LAT_CLEAN', 'LON_CLEAN']].values.tolist())
        if heat_data: HeatMap(heat_data, radius=15, blur=10, name="🔥 Densidade de Obras").add_to(mapa)
    
    if mostrar_todas_obras:
        cluster_todas = MarkerCluster(name="Todas as Obras (Geral)")
        if df_concluidas is not None:
            for _, row in df_concluidas.iterrows():
                lat, lon = row['LAT_CLEAN'], row['LON_CLEAN']
                sv_url = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}"
                areas_especiais = verificar_areas_da_obra(lat, lon) 
                rede_prox = calcular_rede_proxima(lat, lon)
                
                html_popup = f"""<div style="min-width: 250px; font-family: sans-serif;"><h4 style="margin-top: 0; color: #1f77b4; border-bottom: 2px solid #1f77b4; padding-bottom: 5px;">✅ OBRA CONCLUÍDA</h4><table style="width:100%;"><tr><td style="color: #555; padding: 2px;"><b>PROTOCOLO:</b></td><td>{html.escape(str(row.get('PROTOCOLO', 'S/N')))}</td></tr><tr><td style="color: #555; padding: 2px;"><b>NOME:</b></td><td>{html.escape(str(row.get('NOME', 'S/N')))}</td></tr><tr><td style="color: #555; padding: 2px;"><b>REDE ELÉTRICA:</b></td><td>{rede_prox}</td></tr><tr><td style="color: #555; padding: 2px;"><b>ÁREAS:</b></td><td>{areas_especiais}</td></tr><tr><td colspan='2' style='padding-top:10px;'><a href="{sv_url}" target="_blank" style="color: #0066cc; font-weight: bold; text-decoration: none;">👁️ Abrir Street View</a></td></tr></table></div>"""
                
                folium.CircleMarker(location=[lat, lon], radius=5, color='black', weight=1, fill=True, fillColor='#1f77b4', fillOpacity=0.9, tooltip=f"Concluída: {html.escape(str(row.get('PROTOCOLO', 'S/N')))}", popup=folium.Popup(html_popup, max_width=350)).add_to(cluster_todas)
        
        if df_andamento is not None:
            for _, row in df_andamento.iterrows():
                lat, lon = row['LAT_CLEAN'], row['LON_CLEAN']
                cor = 'red' if row['CONFLITO'] else '#2ca02c'
                titulo = "🚨 CONFLITO!" if row['CONFLITO'] else "🚧 EM ANDAMENTO"
                sv_url = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}"
                areas_especiais = verificar_areas_da_obra(lat, lon) 
                rede_prox = calcular_rede_proxima(lat, lon)
                
                html_popup = f"""<div style="min-width: 250px; font-family: sans-serif;"><h4 style="margin-top: 0; color: {cor}; border-bottom: 2px solid {cor}; padding-bottom: 5px;">{titulo}</h4><table style="width:100%;"><tr><td style="color: #555; padding: 2px;"><b>PROTOCOLO:</b></td><td>{html.escape(str(row.get('PROTOCOLO', 'S/N')))}</td></tr><tr><td style="color: #555; padding: 2px;"><b>NOME:</b></td><td>{html.escape(str(row.get('NOME', 'S/N')))}</td></tr><tr><td style="color: #555; padding: 2px;"><b>REDE ELÉTRICA:</b></td><td>{rede_prox}</td></tr><tr><td style="color: #555; padding: 2px;"><b>ÁREAS:</b></td><td>{areas_especiais}</td></tr><tr><td colspan='2' style='padding-top:10px;'><a href="{sv_url}" target="_blank" style="color: #0066cc; font-weight: bold; text-decoration: none;">👁️ Abrir Street View</a></td></tr></table></div>"""
                
                folium.CircleMarker(location=[lat, lon], radius=5, color='black', weight=1, fill=True, fillColor=cor, fillOpacity=0.9, tooltip=f"{titulo}: {html.escape(str(row.get('PROTOCOLO', 'S/N')))}", popup=folium.Popup(html_popup, max_width=350)).add_to(cluster_todas)
        cluster_todas.add_to(mapa)

    if mostrar_concluidas and df_concluidas is not None:
        fg_concluidas = folium.FeatureGroup(name="Obras Concluídas", show=True)
        for _, row in df_concluidas.iterrows():
            protocolo = str(row.get('PROTOCOLO', 'S/N'))
            lat, lon = row['LAT_CLEAN'], row['LON_CLEAN']
            cor_concluida = '#1f77b4'
            sv_url = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}"
            areas_especiais = verificar_areas_da_obra(lat, lon)
            rede_prox = calcular_rede_proxima(lat, lon)
            
            html_popup = f"""<div style="min-width: 250px; font-family: sans-serif;"><h4 style="margin-top: 0; color: {cor_concluida}; border-bottom: 2px solid {cor_concluida}; padding-bottom: 5px;">✅ OBRA CONCLUÍDA</h4><table style="width:100%;"><tr><td style="color: #555; padding: 2px;"><b>PROTOCOLO:</b></td><td>{html.escape(protocolo)}</td></tr><tr><td style="color: #555; padding: 2px;"><b>NOME:</b></td><td>{html.escape(str(row.get('NOME', 'S/N')))}</td></tr><tr><td style="color: #555; padding: 2px;"><b>REDE ELÉTRICA:</b></td><td>{rede_prox}</td></tr><tr><td style="color: #555; padding: 2px;"><b>ÁREAS:</b></td><td>{areas_especiais}</td></tr><tr><td colspan='2' style='padding-top:10px;'><a href="{sv_url}" target="_blank" style="color: #0066cc; font-weight: bold; text-decoration: none;">👁️ Abrir Street View</a></td></tr></table></div>"""
            
            folium.CircleMarker(
                location=[lat, lon], radius=6, color='black', weight=1, fill=True, 
                fillColor=cor_concluida, fillOpacity=1, popup=folium.Popup(html_popup, max_width=350),
                tooltip=f"Obra Concluída: {html.escape(protocolo)}"
            ).add_to(fg_concluidas)
            
        fg_concluidas.add_to(mapa)
            
    if mostrar_conflitantes and df_andamento is not None:
        fg_andamento = folium.FeatureGroup(name="Obras Conflitantes", show=True)
        for _, row in df_andamento.iterrows():
            if not row['CONFLITO']: continue
            lat, lon = row['LAT_CLEAN'], row['LON_CLEAN']
            protocolo = str(row.get('PROTOCOLO', 'S/N'))
            nome_nova = str(row.get('NOME', 'S/N'))
            nome_alvo = str(row.get('NOME_CONCLUIDA', 'S/N'))
            sv_url = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lon}"
            areas_especiais = verificar_areas_da_obra(lat, lon)
            rede_prox = calcular_rede_proxima(lat, lon)
            
            dados_tabela_conflito.append({
                "Protocolo (Nova)": protocolo, "Nome (Nova)": nome_nova,
                "Conflito (Alvo)": row['PROTOCOLO_CONFLITO'], "Nome (Concluída)": nome_alvo,
                "Distância (m)": f"{row['DISTANCIA_CONFLITO']:.1f}m", "Latitude": lat, "Longitude": lon,
                "Google Maps": f"https://www.google.com/maps/search/?api=1&query={lat},{lon}",
                "Street View": sv_url
            })
                
            html_popup = f"""<div style="min-width: 250px; font-family: sans-serif;"><h4 style="margin-top: 0; color: red; border-bottom: 2px solid red; padding-bottom: 5px;">🚨 CONFLITO DETECTADO</h4><table style="width:100%;"><tr><td style="color: #555; padding: 2px;"><b>PROTOCOLO (NOVA):</b></td><td>{html.escape(protocolo)}</td></tr><tr><td style="color: #555; padding: 2px;"><b>NOME (NOVA):</b></td><td>{html.escape(nome_nova)}</td></tr><tr><td style='color: red; padding: 2px;'><b>CONFLITO COM:</b></td><td style='color: red;'>{html.escape(row['PROTOCOLO_CONFLITO'])} ({row['DISTANCIA_CONFLITO']:.1f}m)</td></tr><tr><td style='color: red; padding: 2px;'><b>NOME (CONCLUÍDA):</b></td><td style='color: red;'>{html.escape(nome_alvo)}</td></tr><tr><td style="color: #555; padding: 2px;"><b>REDE ELÉTRICA:</b></td><td>{rede_prox}</td></tr><tr><td style="color: #555; padding: 2px;"><b>ÁREAS:</b></td><td>{areas_especiais}</td></tr><tr><td colspan='2' style='padding-top:10px;'><a href="{sv_url}" target="_blank" style="color: #0066cc; font-weight: bold; text-decoration: none;">👁️ Abrir Street View</a></td></tr></table></div>"""
            folium.CircleMarker(location=[lat, lon], radius=6, color='black', weight=1, fill=True, fillColor='red', fillOpacity=0.9, tooltip=f"Conflito: {html.escape(protocolo)}", popup=folium.Popup(html_popup, max_width=350)).add_to(fg_andamento)
        fg_andamento.add_to(mapa)

# ==========================================
# 🌩️ INTEGRAÇÃO DE RADARES EXTERNOS (STREET VIEW E CLIMA)
# ==========================================
if mostrar_streetview:
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=svv&x={x}&y={y}&z={z}',
        attr='Google Maps Street View',
        name='🛣️ Cobertura Street View',
        overlay=True,
        control=True,
        opacity=0.8
    ).add_to(mapa)

if mostrar_clima:
    url_chuva, url_nuvem = obter_radar_chuva_url()
    if url_nuvem:
        folium.TileLayer(tiles=url_nuvem, attr="RainViewer", name="☁️ Nuvens (Satélite Ao Vivo)", overlay=True, control=True, opacity=0.4, max_native_zoom=12, max_zoom=20).add_to(mapa)
    if url_chuva:
        folium.TileLayer(tiles=url_chuva, attr="RainViewer", name="🌧️ Chuvas Ao Vivo (Radar)", overlay=True, control=True, opacity=0.6, max_native_zoom=12, max_zoom=20).add_to(mapa)
    if not url_chuva and not url_nuvem:
        st.sidebar.warning("⚠️ Serviço de radar climático temporariamente indisponível na API central.")


# O LayerControl superior fica reservado para mapas-base, areas especiais e obras.
# As divisoes internas dos KMZ sao controladas pelo filtro horizontal no rodape.
folium.LayerControl(position='topright', collapsed=True).add_to(mapa)

# Filtro das divisões do KMZ no rodapé. As camadas Leaflet são criadas de forma lazy.
if tipos_presentes_rodape:
    mapa_js = mapa.get_name()
    entradas_js = []
    for tipo in tipos_presentes_rodape:
        rotulo = ROTULOS_REDE.get(tipo, tipo.title())
        cor = CORES_REDE.get(tipo, '#555555')
        carregado = tipo in kmz_payloads
        marcado = tipo in TIPOS_PADRAO_VISIVEIS and carregado
        if tipo in ('REDE PRIMARIA', 'REDE SECUNDARIA'):
            min_zoom = 6 if modo_detalhe else ZOOM_MIN_LINHAS
        elif tipo == 'POSTE':
            min_zoom = ZOOM_MIN_POSTE
        elif tipo == 'TRANSFORMADOR':
            min_zoom = ZOOM_MIN_TRANSFORMADOR
        else:
            min_zoom = ZOOM_MIN_EQUIPAMENTOS
        entradas_js.append({
            'tipo': tipo, 'rotulo': rotulo, 'cor': cor,
            'checked': marcado, 'loaded': carregado,
            'minZoom': min_zoom, 'data': kmz_payloads.get(tipo),
        })

    js_config = json.dumps(entradas_js, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    modo_txt = "Modo detalhe" if modo_detalhe else "Visão geral leve"
    mapa_js_ref = json.dumps(mapa_js)
    js_filtros_kmz = f"""
    <style>
      .kmz-footer-control {{background:rgba(255,255,255,.97);border:1px solid #cfd5df;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.20);padding:7px 10px;margin:0 0 8px 8px;max-width:calc(100vw - 150px);font:12px/1.25 Arial,sans-serif;color:#223}}
      .kmz-footer-title {{font-weight:700;margin-right:8px;color:#0D256C;white-space:nowrap}}
      .kmz-footer-items {{display:flex;flex-wrap:wrap;gap:5px 10px;align-items:center}}
      .kmz-filter-item {{display:flex;align-items:center;gap:4px;white-space:nowrap;cursor:pointer}}
      .kmz-filter-item.disabled {{opacity:.42;cursor:not-allowed}}
      .kmz-swatch {{width:11px;height:11px;border-radius:50%;display:inline-block;border:1px solid #222;box-sizing:border-box}}
      .kmz-swatch.tri {{border-radius:0;width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:11px solid #FFD700;border-top:0;background:transparent!important}}
      .kmz-zoom-note,.kmz-mode-note {{font-size:10px;color:#6b7280;margin-left:2px}}
      @media (max-width:900px) {{.kmz-footer-control {{max-width:calc(100vw - 60px);font-size:11px}}}}
    </style>
    <script>
    (function() {{
      var tries = 0;
      function boot() {{
        tries++;
        var map = window[{mapa_js_ref}];
        if (!map) {{if (tries < 200) setTimeout(boot,100); return;}}
        if (map._kmzLazyInstalled) return;
        map._kmzLazyInstalled = true;
        var cfg = {js_config};
        var layers = {{}};
        var canvasRenderer = L.canvas({{padding:.35}});

        function esc(v) {{return String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');}}
        function popup(p) {{return '<div style="font-family:sans-serif;min-width:240px"><b>Rede:</b> '+esc(p.TIPO_REDE)+'<br><b>Identificação:</b> '+esc(p.NOME)+'<br><b>Alimentador:</b> '+esc(p.ALIMENTADOR)+'<br><b>Localização:</b> '+esc(p.MUNICIPIO)+'<br><b>Coordenadas:</b> '+esc(p.GPS)+'</div>';}}

        function makeLayer(item) {{
          if (!item.loaded || !item.data) return null;
          if (layers[item.tipo]) return layers[item.tipo];
          var tipo = item.tipo;
          var opts = {{
            renderer:canvasRenderer,
            style:function() {{
              if (tipo==='REDE PRIMARIA') return {{color:'#0066FF',weight:4,opacity:.90}};
              if (tipo==='REDE SECUNDARIA') return {{color:'#FF00FF',weight:3,opacity:.90}};
              return {{color:item.cor,weight:2,opacity:.90}};
            }},
            pointToLayer:function(feature,latlng) {{
              if (tipo==='POSTE') return L.circleMarker(latlng,{{renderer:canvasRenderer,radius:4,color:'#000000',weight:1.4,fill:true,fillColor:'#808080',fillOpacity:1}});
              if (tipo==='TRANSFORMADOR') {{
                var icon=L.divIcon({{className:'kmz-trafo-icon',html:'<div style="width:0;height:0;border-left:7px solid transparent;border-right:7px solid transparent;border-bottom:13px solid #FFD700;filter:drop-shadow(0 0 1px #FFD700)"></div>',iconSize:[14,13],iconAnchor:[7,7]}});
                return L.marker(latlng,{{icon:icon,keyboard:false}});
              }}
              return L.circleMarker(latlng,{{renderer:canvasRenderer,radius:6,color:item.cor,weight:2,fill:true,fillColor:item.cor,fillOpacity:1}});
            }},
            onEachFeature:function(feature,layer) {{var p=feature.properties||{{}};layer.bindTooltip(esc(p.TIPO_REDE)+': '+esc(p.NOME),{{sticky:true}});layer.bindPopup(popup(p),{{maxWidth:350}});}}
          }};
          layers[tipo]=L.geoJSON(item.data,opts);
          return layers[tipo];
        }}

        var control=L.control({{position:'bottomleft'}});
        control.onAdd=function() {{
          var div=L.DomUtil.create('div','kmz-footer-control');
          var h='<div class="kmz-footer-items"><span class="kmz-footer-title">Camadas KMZ:</span>';
          cfg.forEach(function(item,idx) {{
            var disabled=item.loaded?'':' disabled';
            var checked=item.checked?' checked':'';
            var disAttr=item.loaded?'':' disabled';
            var cls=item.tipo==='TRANSFORMADOR'?'kmz-swatch tri':'kmz-swatch';
            var title=item.loaded?('Visível a partir do zoom '+item.minZoom):'Selecione até 3 alimentadores ou use Localizar alimentador para liberar esta camada';
            h+='<label class="kmz-filter-item'+disabled+'" title="'+title+'"><input type="checkbox" data-kmz="'+idx+'"'+checked+disAttr+'><span class="'+cls+'" style="background:'+item.cor+'"></span><span>'+item.rotulo+'</span><span class="kmz-zoom-note">z'+item.minZoom+'+</span></label>';
          }});
          h+='<span class="kmz-mode-note">{modo_txt}</span></div>';
          div.innerHTML=h;L.DomEvent.disableClickPropagation(div);L.DomEvent.disableScrollPropagation(div);return div;
        }};
        control.addTo(map);

        function apply() {{
          var z=map.getZoom();var root=map.getContainer().querySelector('.kmz-footer-control');
          cfg.forEach(function(item,idx) {{
            var cb=root?root.querySelector('input[data-kmz="'+idx+'"]'):null;
            var wants=!!(item.loaded&&cb&&cb.checked&&z>=item.minZoom);
            var layer=layers[item.tipo];
            if (wants) {{if(!layer) layer=makeLayer(item);if(layer&&!map.hasLayer(layer)) map.addLayer(layer);}}
            else if(layer&&map.hasLayer(layer)) map.removeLayer(layer);
            if(cb) cb.parentElement.style.opacity=item.loaded?(z>=item.minZoom?'1':'.60'):'.42';
          }});
        }}
        var root=map.getContainer().querySelector('.kmz-footer-control');if(root) root.addEventListener('change',apply);
        map.on('zoomend',apply);map.on('baselayerchange',function(){{setTimeout(apply,20);}});apply();
      }}
      boot();
    }})();
    </script>
    """
    mapa.get_root().html.add_child(folium.Element(js_filtros_kmz))

# -------------------------------------------------------------
# 5. TABELA INTELIGENTE E BOTÃO DE EXPORTAÇÃO
# -------------------------------------------------------------
zoom_lat, zoom_lon = None, None

with table_container:
    if mostrar_conflitantes and msg_obras == "OK" and len(dados_tabela_conflito) > 0:
        st.markdown("---")
        st.markdown(f"<h3 style='color: #d62728;'>🚨 Relatório de Obras Sobrepostas (Total: {len(dados_tabela_conflito)})</h3>", unsafe_allow_html=True)
        st.markdown("As obras abaixo estão em andamento, mas encontram-se no raio de 50 metros de uma obra já dada como concluída.<br>💡 **DICA INTERATIVA:** Clique em qualquer linha da tabela abaixo para dar zoom exato na obra no mapa!", unsafe_allow_html=True)
        
        df_tabela = pd.DataFrame(dados_tabela_conflito)
        try:
            event = st.dataframe(
                df_tabela, use_container_width=True, on_select="rerun", selection_mode="single_row",
                column_config={"Google Maps": st.column_config.LinkColumn("📍 Rota Geográfica", display_text="Abrir Maps"), "Street View": st.column_config.LinkColumn("👁️ Visão de Rua", display_text="Abrir 360º")}
            )
            if hasattr(event, 'selection') and event.selection.rows:
                idx = event.selection.rows[0]
                zoom_lat, zoom_lon = float(df_tabela.iloc[idx]['Latitude']), float(df_tabela.iloc[idx]['Longitude'])
        except Exception: st.dataframe(df_tabela, use_container_width=True)
        
        csv = df_tabela.to_csv(index=False).encode('utf-8-sig')
        st.download_button(label="📥 Baixar Relatório (CSV)", data=csv, file_name="conflitos.csv", mime="text/csv", type="primary")

    if (mostrar_concluidas or mostrar_conflitantes or mostrar_heatmap or mostrar_todas_obras) and msg_obras == "OK":
        if df_invalidas is not None and not df_invalidas.empty:
            st.markdown("---")
            with st.expander(f"⚠️ Monitor de Qualidade de Dados ({len(df_invalidas)} Inconsistências na Planilha)"):
                st.markdown("As obras abaixo foram **ignoradas no mapa** porque estão com o GPS em branco, zerado (0,0) ou fora do território brasileiro. Corrija na planilha SISCO para que elas sejam processadas.")
                cols_to_show = [c for c in ['PROTOCOLO', 'TIPO NOTA', 'MUNICIPIO', 'LATITUDE', 'LONGITUDE', 'STATUS SISCO'] if c in df_invalidas.columns]
                st.dataframe(df_invalidas[cols_to_show], use_container_width=True)

# -------------------------------------------------------------
# 6. GERENCIAMENTO DE ZOOM E RENDERIZAÇÃO FINAL DO MAPA
# -------------------------------------------------------------
# Prioridade de enquadramento: tabela/pesquisa -> alimentador escolhido -> municipio.
if zoom_lat is not None and zoom_lon is not None:
    mapa.fit_bounds([[zoom_lat - 0.001, zoom_lon - 0.001], [zoom_lat + 0.001, zoom_lon + 0.001]], padding=(30, 30), max_zoom=18)
elif busca_lat is not None and busca_lon is not None:
    mapa.fit_bounds([[busca_lat - 0.001, busca_lon - 0.001], [busca_lat + 0.001, busca_lon + 0.001]], padding=(30, 30), max_zoom=18)
elif busca_lats and busca_lons:
    mapa.fit_bounds([[min(busca_lats), min(busca_lons)], [max(busca_lats), max(busca_lons)]], padding=(35, 35), max_zoom=18)
elif alimentador_foco != "Todos / visão geral" and not df.empty:
    df_foco = df[df['ALIMENTADOR'] == alimentador_foco]
    foco_lats, foco_lons = [], []
    for _, row in df_foco.iterrows():
        coords = row.get('COORDS')
        if not coords:
            continue
        if row.get('TIPO_GEOMETRIA') == 'Ponto':
            foco_lats.append(float(coords[0])); foco_lons.append(float(coords[1]))
        else:
            for pt in coords:
                foco_lats.append(float(pt[0])); foco_lons.append(float(pt[1]))
    if foco_lats and foco_lons:
        if min(foco_lats) == max(foco_lats) and min(foco_lons) == max(foco_lons):
            lat0, lon0 = foco_lats[0], foco_lons[0]
            mapa.fit_bounds([[lat0 - 0.002, lon0 - 0.002], [lat0 + 0.002, lon0 + 0.002]], padding=(45, 45), max_zoom=16)
        else:
            mapa.fit_bounds(
                [[min(foco_lats), min(foco_lons)], [max(foco_lats), max(foco_lons)]],
                padding=(45, 45), max_zoom=16,
            )
elif municipios_sel and geo_data_ibge:
    mun_foco_lats, mun_foco_lons = [], []
    for feature in geo_data_ibge['features']:
        if feature['properties'].get('MUNICIPIO') in municipios_sel:
            geom = feature['geometry']
            if geom['type'] == 'Polygon':
                for pt in geom['coordinates'][0]: mun_foco_lats.append(pt[1]); mun_foco_lons.append(pt[0])
            elif geom['type'] == 'MultiPolygon':
                for poly in geom['coordinates']:
                    for pt in poly[0]: mun_foco_lats.append(pt[1]); mun_foco_lons.append(pt[0])
    if mun_foco_lats and mun_foco_lons:
        mapa.fit_bounds([[min(mun_foco_lats), min(mun_foco_lons)], [max(mun_foco_lats), max(mun_foco_lons)]], padding=(35, 35))

with map_container:
    # Nao devolvemos zoom/center/bounds para o Python. Pan e zoom ficam 100% no Leaflet,
    # evitando reruns e mantendo a navegacao continua e fluida.
    st_folium(
        mapa,
        use_container_width=True,
        height=850,
        returned_objects=[],
        key="mapa_principal_v6",
    )

