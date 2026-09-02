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
from folium.plugins import HeatMap
import gc
from streamlit_folium import st_folium
import html
from concurrent.futures import ThreadPoolExecutor
from scipy.spatial import cKDTree

st.set_page_config(page_title="Visualizador de Malha", page_icon="🗺️", layout="wide")

if not os.path.exists("database/redes"):
    os.makedirs("database/redes", exist_ok=True)

# ==========================================
# 1. FUNÇÕES BASE, PLANILHA E GEOLOCALIZAÇÃO
# ==========================================
def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', str(input_str))
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])

def latlon_to_xyz(lat, lon):
    """Converte Latitude e Longitude para coordenadas 3D cartesianas (metros)"""
    R = 6371000.0 # Raio da Terra em metros
    lat_rad, lon_rad = math.radians(lat), math.radians(lon)
    return R * math.cos(lat_rad) * math.cos(lon_rad), R * math.cos(lat_rad) * math.sin(lon_rad), R * math.sin(lat_rad)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # Raio da Terra em km
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
        st.sidebar.error(f"🚨 Planilha '{file_path}' não encontrada! Verifique o nome.")
    else:
        try:
            df_base = pd.read_excel(file_path)
            for _, row in df_base.iterrows():
                mun = remove_accents(str(row.get('MunicIpio', ''))).upper().strip()
                reg = str(row.get('Regional', '')).strip().upper()
                if mun and reg and reg != 'NAN':
                    mun_to_reg[mun] = reg
        except Exception as e:
            st.sidebar.error(f"🚨 Erro ao ler a planilha: {e}")
    
    overrides_centro = [
        'SANTA LUZIA', 'CONCEICAO DO LAGO-ACU', 'CONCEICAO DO LAGO ACU', 
        'PINDARE-MIRIM', 'PINDARE MIRIM', 'OLHO DAGUA DAS CUNHAS', 
        'OLHO D\'AGUA DAS CUNHAS', 'GOVERNADOR LUIZ ROCHA'
    ]
    for mun in overrides_centro:
        if mun not in mun_to_reg:
            mun_to_reg[mun] = 'CENTRO'
            
    return mun_to_reg

@st.cache_data(show_spinner=False)
def get_base_geojson():
    mun_to_reg = load_base_mapping()
    url_geojson = "https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-21-mun.json"
    try:
        resp = requests.get(url_geojson, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        geo_data = resp.json()
    except:
        return None

    reg_colors = {
        'LESTE': '#1f77b4', 'CENTRO': '#d62728', 'NOROESTE': '#ffed6f', 
        'NORTE': '#ff7f0e', 'SUL': '#8fbc8f', 'DESCONHECIDO': '#cccccc'
    }

    for feature in geo_data['features']:
        mun_name = feature['properties']['name']
        mun_name_norm = remove_accents(mun_name).upper().strip()
        reg = mun_to_reg.get(mun_name_norm, "DESCONHECIDO")
        
        feature['properties']['REGIONAL'] = reg
        feature['properties']['MUNICIPIO'] = mun_name_norm
        feature['properties']['fillColor'] = reg_colors.get(reg, '#cccccc')
        
    return geo_data

def is_point_in_polygon(lon, lat, polygon):
    inside = False
    for i in range(len(polygon)):
        p1x, p1y = polygon[i]
        p2x, p2y = polygon[(i + 1) % len(polygon)]
        if ((p1y > lat) != (p2y > lat)) and (lon < (p2x - p1x) * (lat - p1y) / (p2y - p1y + 1e-9) + p1x):
            inside = not inside
    return inside

def get_municipio_by_coord(lon, lat, geo_data):
    if not geo_data: return "N/A", "N/A"
    for feature in geo_data['features']:
        geom = feature['geometry']
        mun = feature['properties'].get('MUNICIPIO', 'N/A')
        reg = feature['properties'].get('REGIONAL', 'N/A')
        
        if geom['type'] == 'Polygon':
            for ring in geom['coordinates']:
                if is_point_in_polygon(lon, lat, ring): return mun, reg
        elif geom['type'] == 'MultiPolygon':
            for poly in geom['coordinates']:
                for ring in poly:
                    if is_point_in_polygon(lon, lat, ring): return mun, reg
    return "N/A", "N/A"

def extrair_coordenadas_vis(texto_coords):
    pontos = []
    for coord in texto_coords.strip().split():
        partes = coord.split(',')
        if len(partes) >= 2:
            try:
                lon = float(partes[0].strip().replace(',', '.'))
                lat = float(partes[1].strip().replace(',', '.'))
                if lat != 0.0 and lon != 0.0 and -35.0 <= lat <= 5.0 and -75.0 <= lon <= -30.0:
                    pontos.append([lat, lon]) 
            except:
                continue
    return pontos

def ler_kml_para_geojson(caminho_arquivo, cor_hex):
    if not os.path.exists(caminho_arquivo): return None
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            kml_str = f.read()
        kml_str = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', kml_str)
        root = ET.fromstring(kml_str)
        
        features = []
        for placemark in root.findall('.//Placemark'):
            name_tag = placemark.find('name')
            nome = name_tag.text.strip() if name_tag is not None and name_tag.text else "Área Demarcada"
            
            for simple_data in placemark.findall('.//SimpleData'):
                if simple_data.attrib.get('name') in ['nm_municip', 'fase_ti', 'etnia', 'nome']:
                    if simple_data.text: nome += f" | {simple_data.text}"
            
            for poly in placemark.findall('.//Polygon//coordinates'):
                if poly.text:
                    coords = []
                    for coord_str in poly.text.strip().split():
                        partes = coord_str.split(',')
                        if len(partes) >= 2: coords.append([float(partes[0]), float(partes[1])])
                    if coords:
                        features.append({"type": "Feature", "properties": {"NOME": nome, "COR": cor_hex}, "geometry": {"type": "Polygon", "coordinates": [coords]}})
                        
            for pt in placemark.findall('.//Point/coordinates'):
                if pt.text:
                    partes = pt.text.strip().split(',')
                    if len(partes) >= 2:
                        features.append({"type": "Feature", "properties": {"NOME": nome, "COR": cor_hex}, "geometry": {"type": "Point", "coordinates": [float(partes[0]), float(partes[1])]}})
        
        if features: return {"type": "FeatureCollection", "features": features}
        return None
    except: return None

@st.cache_data(show_spinner=False)
def get_kml_cached(path, color):
    return ler_kml_para_geojson(path, color)

def processar_um_kmz(f_name, f_bytes, base_map, geo_data):
    dict_cores = {
        'REDE PRIMÁRIA': '#e6194b', 'REDE PRIMARIA': '#e6194b',
        'REDE SECUNDÁRIA': '#4363d8', 'REDE SECUNDARIA': '#4363d8',
        'POSTE': '#808080', 'TRANSFORMADOR': '#f58231', 
        'CHAVE': '#3cb44b', 'REGULADOR': '#911eb4', 
        'RELIGADOR': '#46f0f0', 'CAPACITOR': '#ffe119',
        'SUBESTAÇÃO': '#000000', 'SUBESTACAO': '#000000'
    }

    nome_arquivo = f_name.upper().replace('.KMZ', '').replace('.KML', '')
    caminho_db = f"database/redes/{nome_arquivo}.pkl"
    
    if os.path.exists(caminho_db): return None
        
    conteudo_kml = ""
    if f_name.lower().endswith('.kmz'):
        try:
            with zipfile.ZipFile(io.BytesIO(f_bytes), 'r') as z:
                for item in z.namelist():
                    if item.lower().endswith('.kml'):
                        conteudo_kml = z.read(item).decode('utf-8', errors='ignore')
                        break
        except Exception: return None
    else:
        try: conteudo_kml = f_bytes.decode('utf-8', errors='ignore')
        except: return None
    
    conteudo_kml = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', conteudo_kml)
    try: root = ET.fromstring(conteudo_kml)
    except Exception: return None

    municipio = "N/A"
    regional = "N/A"
    
    mun_match = re.search(r'name=["\'](?:MUNICIPIO|CIDADE)["\'][^>]*>(.*?)</', conteudo_kml, re.IGNORECASE)
    if mun_match: 
        municipio = mun_match.group(1).strip().upper()
        mun_norm = remove_accents(municipio)
        if mun_norm in base_map:
            regional = base_map[mun_norm]

    if regional == "N/A":
        reg_match = re.search(r'name=["\'](?:REGIONAL|REGIAO)["\'][^>]*>(.*?)</', conteudo_kml, re.IGNORECASE)
        if reg_match: regional = reg_match.group(1).strip().upper()

    if regional == "N/A":
        sigla_match = re.search(r'\[([A-Z]{3})\]', nome_arquivo)
        if sigla_match: regional = sigla_match.group(1)

    registros_flat = []
    primeira_coord = None
    
    for folder in root.findall('.//Folder'):
        name_tag = folder.find('name')
        if name_tag is not None and name_tag.text:
            nome_pasta = name_tag.text.strip().upper()
            if "CEMAR" in nome_pasta or nome_arquivo in nome_pasta: continue
            cor_elemento = dict_cores.get(nome_pasta, '#333333')
            
            for placemark in folder.findall('.//Placemark'):
                pm_name_tag = placemark.find('name')
                nome_elemento = pm_name_tag.text.strip() if pm_name_tag is not None and pm_name_tag.text else "S/N"
                
                for ls in placemark.findall('.//LineString/coordinates'):
                    if ls.text:
                        coords = extrair_coordenadas_vis(ls.text)
                        if len(coords) > 1:
                            if not primeira_coord: primeira_coord = coords[0]
                            registros_flat.append({
                                'ALIMENTADOR': nome_arquivo, 'REGIONAL': regional, 'MUNICIPIO': municipio,
                                'TIPO_GEOMETRIA': 'Linha', 'TIPO_REDE': nome_pasta, 'NOME': nome_elemento,
                                'COORDS': coords, 'COR': cor_elemento
                            })
                        
                for pt in placemark.findall('.//Point/coordinates'):
                    if pt.text:
                        coords = extrair_coordenadas_vis(pt.text)
                        if len(coords) > 0:
                            if not primeira_coord: primeira_coord = coords[0]
                            registros_flat.append({
                                'ALIMENTADOR': nome_arquivo, 'REGIONAL': regional, 'MUNICIPIO': municipio,
                                'TIPO_GEOMETRIA': 'Ponto', 'TIPO_REDE': nome_pasta, 'NOME': nome_elemento,
                                'COORDS': coords[0], 'COR': cor_elemento
                            })
    
    if municipio == "N/A" and primeira_coord is not None and geo_data is not None:
        mun_descob, reg_descob = get_municipio_by_coord(primeira_coord[1], primeira_coord[0], geo_data)
        if mun_descob != "N/A":
            municipio = mun_descob
            regional = reg_descob if reg_descob != "N/A" else regional
            for r in registros_flat:
                r['MUNICIPIO'] = municipio
                r['REGIONAL'] = regional

    if registros_flat:
        return (caminho_db, pd.DataFrame(registros_flat))
    return None

def processar_e_salvar_kmz_paralelo(arquivos):
    base_map = load_base_mapping()
    geo_data = get_base_geojson()
    novos_processados = 0
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for f in arquivos:
            futures.append(executor.submit(processar_um_kmz, f.name, f.getvalue(), base_map, geo_data))
        for future in futures:
            resultado = future.result()
            if resultado:
                caminho_db, df_alimentador = resultado
                df_alimentador.to_pickle(caminho_db)
                novos_processados += 1
    return novos_processados

@st.cache_data(show_spinner=False)
def carregar_banco_redes():
    dfs = []
    arquivos = [f for f in os.listdir("database/redes") if f.endswith('.pkl')]
    for f in arquivos:
        try: dfs.append(pd.read_pickle(f"database/redes/{f}"))
        except: pass
    if dfs: return pd.concat(dfs, ignore_index=True)
    return pd.DataFrame()

@st.cache_data(show_spinner=False)
def carregar_e_cruzar_obras():
    file_path = "BASE_LEVANTAMENTO_ATUALIZADA.xlsx"
    if not os.path.exists(file_path):
        return "Arquivo 'BASE_LEVANTAMENTO_ATUALIZADA.xlsx' não encontrado.", None, None
        
    try:
        df_obras = pd.read_excel(file_path)
        
        status_sisco_col = next((c for c in df_obras.columns if 'STATUS SISCO' in str(c).upper()), None)
        status_list_col = next((c for c in df_obras.columns if 'STATUS LIST' in str(c).upper()), None)
        lat_col = next((c for c in df_obras.columns if 'LATITUDE' in str(c).upper() or 'LAT' == str(c).upper()), None)
        lon_col = next((c for c in df_obras.columns if 'LONGITUDE' in str(c).upper() or 'LON' == str(c).upper()), None)
        
        if not all([status_sisco_col, status_list_col, lat_col, lon_col]):
            return "Erro: Colunas obrigatórias ausentes na planilha (Status ou Coordenadas).", None, None
            
        if df_obras[lat_col].dtype == object: df_obras[lat_col] = df_obras[lat_col].astype(str).str.replace(',', '.')
        if df_obras[lon_col].dtype == object: df_obras[lon_col] = df_obras[lon_col].astype(str).str.replace(',', '.')
            
        df_obras['LAT_CLEAN'] = pd.to_numeric(df_obras[lat_col], errors='coerce')
        df_obras['LON_CLEAN'] = pd.to_numeric(df_obras[lon_col], errors='coerce')
        df_obras = df_obras.dropna(subset=['LAT_CLEAN', 'LON_CLEAN'])
        
        mask_valid_coords = (
            (df_obras['LAT_CLEAN'] != 0.0) & 
            (df_obras['LON_CLEAN'] != 0.0) & 
            (df_obras['LAT_CLEAN'] >= -35.0) & 
            (df_obras['LAT_CLEAN'] <= 5.0) & 
            (df_obras['LON_CLEAN'] >= -75.0) & 
            (df_obras['LON_CLEAN'] <= -30.0)
        )
        df_obras = df_obras[mask_valid_coords]
        
        mask_concluida = df_obras[status_sisco_col].astype(str).str.contains('CONCLU', case=False, na=False)
        df_concluidas = df_obras[mask_concluida].copy()
        
        def normalizar(x): return remove_accents(str(x)).upper().strip()
        df_obras['STATUS_LIST_NORM'] = df_obras[status_list_col].apply(normalizar)
        
        status_alvos = ['0', 'EM LEVANTAMENTO', 'CORRECAO DE LEVANTAMENTO']
        mask_andamento = df_obras['STATUS_LIST_NORM'].isin(status_alvos)
        df_andamento = df_obras[mask_andamento & (~mask_concluida)].copy()
        
        df_andamento['CONFLITO'] = False
        df_andamento['PROTOCOLO_CONFLITO'] = ""
        df_andamento['DISTANCIA_CONFLITO'] = 0.0
        
        if not df_concluidas.empty and not df_andamento.empty:
            pts_concluidas = [latlon_to_xyz(row['LAT_CLEAN'], row['LON_CLEAN']) for _, row in df_concluidas.iterrows()]
            arvore_kdtree = cKDTree(pts_concluidas)
            
            conflitos_flags = []
            conflitos_protos = []
            conflitos_dists = []
            
            for _, row in df_andamento.iterrows():
                xyz = latlon_to_xyz(row['LAT_CLEAN'], row['LON_CLEAN'])
                _, idx_mais_proximo = arvore_kdtree.query(xyz)
                
                obra_concluida_proxima = df_concluidas.iloc[idx_mais_proximo]
                distancia_exata_m = haversine(row['LAT_CLEAN'], row['LON_CLEAN'], obra_concluida_proxima['LAT_CLEAN'], obra_concluida_proxima['LON_CLEAN']) * 1000
                
                # RAIO DETECTADO ATUALIZADO PARA 50m
                if distancia_exata_m <= 50:
                    conflitos_flags.append(True)
                    conflitos_protos.append(str(obra_concluida_proxima.get('PROTOCOLO', 'S/N')))
                    conflitos_dists.append(distancia_exata_m)
                else:
                    conflitos_flags.append(False)
                    conflitos_protos.append("")
                    conflitos_dists.append(0.0)
                    
            df_andamento['CONFLITO'] = conflitos_flags
            df_andamento['PROTOCOLO_CONFLITO'] = conflitos_protos
            df_andamento['DISTANCIA_CONFLITO'] = conflitos_dists
            
        return "OK", df_concluidas, df_andamento
        
    except Exception as e:
        return f"Erro processando dados: {str(e)}", None, None


# ==========================================
# 2. ESTRUTURA DA TELA E CONTAINERS
# ==========================================
st.markdown("<h2 style='color: #0D256C;'>🗺️ Visualizador Oficial de Malha (Satélite Integrado)</h2>", unsafe_allow_html=True)
st.markdown("O sistema usa **Inteligência Espacial** para descobrir o município e Scipy para pesquisa instantânea de coordenadas!")

# Organizando a ordem de renderização
kpi_container = st.empty()
map_container = st.empty()
table_container = st.container()

df = carregar_banco_redes()
base_map = load_base_mapping()
geo_data_ibge = get_base_geojson()

# ==========================================
# 3. INTERFACE E FILTROS LATERAIS
# ==========================================
with st.sidebar:
    st.markdown("### 📥 1. Upload de Redes")
    arquivos_upados = st.file_uploader("Arraste novos KMZs aqui", type=["kmz", "kml"], accept_multiple_files=True)
    
    if arquivos_upados:
        if st.button(f"💾 Processar e Salvar {len(arquivos_upados)} Arquivo(s)", type="primary", use_container_width=True):
            qtd_total_processados = 0
            tamanho_lote = 3
            total_lotes = math.ceil(len(arquivos_upados) / tamanho_lote)
            barra_progresso = st.progress(0.0)
            texto_status = st.empty()
            
            for i in range(0, len(arquivos_upados), tamanho_lote):
                lote_atual = (i // tamanho_lote) + 1
                lote_arquivos = arquivos_upados[i:i+tamanho_lote]
                texto_status.text(f"⏳ Processando Lote {lote_atual} de {total_lotes}...")
                qtd_total_processados += processar_e_salvar_kmz_paralelo(lote_arquivos)
                barra_progresso.progress(lote_atual / total_lotes)
                gc.collect() 

            if qtd_total_processados > 0:
                st.success(f"✅ {qtd_total_processados} novos Alimentadores salvos!")
                carregar_banco_redes.clear()
                time.sleep(1.5)
                st.rerun()
            else:
                st.info("Nenhum arquivo novo foi processado.")

    st.markdown("---")
    st.markdown("### 🔎 2. Pesquisas Inteligentes")
    tab_nome, tab_coord = st.tabs(["📝 Por Nome/ID", "📍 Por Coordenada"])
    termo_pesquisa = ""
    busca_lat = None
    busca_lon = None
    
    with tab_nome:
        termo_pesquisa = st.text_input("Nome/Num. Poste ou Trafo:", placeholder="Ex: 554930...").strip().upper()
    with tab_coord:
        c_lat, c_lon = st.columns(2)
        with c_lat: lat_input = st.text_input("Latitude:", placeholder="Ex: -5.532")
        with c_lon: lon_input = st.text_input("Longitude:", placeholder="Ex: -47.432")
        if lat_input and lon_input:
            try:
                b_lat = float(lat_input.replace(',', '.').strip())
                b_lon = float(lon_input.replace(',', '.').strip())
                if -35.0 <= b_lat <= 5.0 and -75.0 <= b_lon <= -30.0:
                    busca_lat, busca_lon = b_lat, b_lon
                else: st.warning("⚠️ Coordenada fora do Brasil.")
            except: st.warning("⚠️ Formato inválido.")

    st.markdown("---")
    st.markdown("### 🔍 3. Filtros Geográficos")
    lista_regioes = sorted(list(set(base_map.values()))) if base_map else ["CENTRO", "LESTE", "NOROESTE", "NORTE", "SUL"]
    regioes_sel = st.multiselect("📍 Regional:", lista_regioes)
    
    lista_municipios = []
    for mun, reg in base_map.items():
        if not regioes_sel or reg in regioes_sel:
            lista_municipios.append(mun)
    lista_municipios = sorted(lista_municipios)
    municipios_sel = st.multiselect("🏙️ Município (Foco e Contorno):", lista_municipios)
    
    df_filt = df.copy()
    if not df.empty:
        if regioes_sel: df_filt = df_filt[df_filt['REGIONAL'].isin(regioes_sel)]
        if municipios_sel: df_filt = df_filt[df_filt['MUNICIPIO'].isin(municipios_sel)]
    
    lista_alimentadores = sorted(df_filt['ALIMENTADOR'].unique().tolist()) if not df_filt.empty else []
    alim_sel = st.multiselect("⚡ Alimentador:", lista_alimentadores)
    alimentadores_visiveis = alim_sel if alim_sel else lista_alimentadores

    camadas_ativas = {}
    if not df.empty:
        st.markdown("---")
        st.markdown("### 🗂️ 4. Camadas (Desempenho)")
        for alim in alimentadores_visiveis:
            st.markdown(f"**{alim}**")
            lista_camadas_alim = sorted(df[df['ALIMENTADOR'] == alim]['TIPO_REDE'].unique().tolist())
            camadas_essenciais = ['REDE PRIMÁRIA', 'REDE PRIMARIA', 'REDE SECUNDÁRIA', 'REDE SECUNDARIA', 'TRANSFORMADOR', 'POSTE', 'CAPACITOR', 'CHAVE', 'REGULADOR', 'RELIGADOR', 'SUBESTAÇÃO', 'SUBESTACAO']
            camadas_default = [c for c in lista_camadas_alim if c in camadas_essenciais]
            camadas_ativas[alim] = st.multiselect("Visibilidade:", lista_camadas_alim, default=camadas_default, key=f"ms_{alim}")
            
    st.markdown("---")
    st.markdown("### 🗺️ 5. Áreas Especiais")
    mostrar_quilombos = st.checkbox("🟠 Áreas Quilombolas", value=False)
    mostrar_indigenas = st.checkbox("🟢 Terras Indígenas", value=False)
    mostrar_arqueologia = st.checkbox("🔵 Sítios Arqueológicos", value=False)
    mostrar_uc_federal = st.checkbox("🟡 UC Federal", value=False)
    mostrar_uc_estadual = st.checkbox("🟡 UC Estadual", value=False)
    mostrar_uc_municipal = st.checkbox("🟡 UC Municipal", value=False)
    
    st.markdown("---")
    st.markdown("### 🚧 6. Obras e Projetos")
    mostrar_concluidas = st.checkbox("🔵 OBRAS CONCLUÍDAS (Raio 50m)", value=False)
    mostrar_conflitantes = st.checkbox("🚨 OBRAS CONFLITANTES (Raio 50m)", value=False)
    mostrar_heatmap = st.checkbox("🔥 Mapa de Calor (Densidade de Obras)", value=False)
    
    msg_obras, df_concluidas, df_andamento = "OK", None, None
    if mostrar_concluidas or mostrar_conflitantes or mostrar_heatmap:
        msg_obras, df_concluidas, df_andamento = carregar_e_cruzar_obras()
        if msg_obras != "OK":
            st.sidebar.warning(f"⚠️ {msg_obras}")
        else:
            # FILTRO TEMPORAL NOVO
            if 'DATA ABERTURA' in df_andamento.columns:
                df_andamento['DATA ABERTURA_DT'] = pd.to_datetime(df_andamento['DATA ABERTURA'], errors='coerce')
                min_date = df_andamento['DATA ABERTURA_DT'].dropna().min()
                max_date = df_andamento['DATA ABERTURA_DT'].dropna().max()
                if pd.notnull(min_date) and pd.notnull(max_date):
                    data_filtro = st.date_input("📅 Filtrar Conflitos (Data de Abertura):", [min_date.date(), max_date.date()])
                    if len(data_filtro) == 2:
                        mask_data = (df_andamento['DATA ABERTURA_DT'].dt.date >= data_filtro[0]) & (df_andamento['DATA ABERTURA_DT'].dt.date <= data_filtro[1])
                        df_andamento = df_andamento[mask_data]

            qtd_conflitos = df_andamento['CONFLITO'].sum()
            if mostrar_concluidas:
                st.sidebar.success(f"🔵 {len(df_concluidas)} Concluídas analisadas")
            if mostrar_conflitantes:
                if qtd_conflitos > 0: st.sidebar.error(f"🚨 {qtd_conflitos} CONFLITOS ISOLADOS!")
                else: st.sidebar.success("🎉 Nenhuma obra em conflito!")
            
    st.markdown("---")
    st.markdown("### 🗑️ Gerenciar Malha Local")
    alim_para_deletar = st.selectbox("Apagar Alimentador do Banco:", ["Selecione..."] + sorted(df['ALIMENTADOR'].unique().tolist()) if not df.empty else ["Selecione..."])
    if alim_para_deletar != "Selecione...":
        if st.button("❌ Excluir Permanentemente", use_container_width=True):
            caminho_del = f"database/redes/{alim_para_deletar}.pkl"
            if os.path.exists(caminho_del):
                os.remove(caminho_del)
                carregar_banco_redes.clear()
                st.success("Excluído!")
                time.sleep(1)
                st.rerun()

# ==========================================
# DASHBOARD DE INDICADORES (KPIs)
# ==========================================
with kpi_container.container():
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("⚡ Alimentadores Mapeados", len(df['ALIMENTADOR'].unique()) if not df.empty else 0)
    
    if msg_obras == "OK" and df_concluidas is not None:
        c2.metric("🔵 Obras Concluídas", len(df_concluidas))
        c3.metric("🟢 Obras em Andamento", len(df_andamento))
        c4.metric("🚨 Conflitos (50m)", df_andamento['CONFLITO'].sum() if not df_andamento.empty else 0)
    else:
        c2.metric("🔵 Obras Concluídas", 0)
        c3.metric("🟢 Obras em Andamento", 0)
        c4.metric("🚨 Conflitos (50m)", 0)
    st.markdown("---")

# ==========================================
# 4. CONSTRUÇÃO DO MAPA FOLIUM (BASE)
# ==========================================
mapa = folium.Map(location=[-5.2, -45.0], zoom_start=6, tiles=None, prefer_canvas=True)

folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Satélite (Google Maps)', overlay=False, control=True, max_zoom=20).add_to(mapa)
folium.TileLayer(tiles='OpenStreetMap', name='Mapa Base (Limpo)', overlay=False, control=True, max_zoom=20).add_to(mapa)

if geo_data_ibge:
    def style_function(feature):
        reg_mun = feature['properties'].get('MUNICIPIO', '')
        reg_name = feature['properties'].get('REGIONAL', '')
        cor_regiao = feature['properties']['fillColor']
        if municipios_sel:
            if reg_mun in municipios_sel: return {'fillColor': 'transparent', 'color': '#FF00FF', 'weight': 4, 'fillOpacity': 0}
            else: return {'fillColor': 'transparent', 'color': 'transparent', 'weight': 0}
        elif regioes_sel:
            if reg_name in regioes_sel: return {'fillColor': cor_regiao, 'color': cor_regiao, 'weight': 1, 'fillOpacity': 0.75}
            else: return {'fillColor': 'transparent', 'color': 'transparent', 'weight': 0}
        return {'fillColor': cor_regiao, 'color': cor_regiao, 'weight': 1, 'fillOpacity': 0.75}

    folium.GeoJson(geo_data_ibge, name="Divisão IBGE (Maranhão)", style_function=style_function, tooltip=folium.features.GeoJsonTooltip(fields=['name', 'REGIONAL'], aliases=['Município:', 'Regional:'], style="background-color: white; color: #333; font-family: arial; font-size: 12px; padding: 10px;"), zoom_on_click=False, show=True).add_to(mapa)

todas_lats, todas_lons = [], []
busca_lats, busca_lons = [], []

if not df.empty:
    df_mapa = df.copy()
    if regioes_sel: df_mapa = df_mapa[df_mapa['REGIONAL'].isin(regioes_sel)]
    if municipios_sel: df_mapa = df_mapa[df_mapa['MUNICIPIO'].isin(municipios_sel)]
    df_mapa = df_mapa[df_mapa['ALIMENTADOR'].isin(alimentadores_visiveis)]

    mask_camadas = pd.Series(False, index=df_mapa.index)
    for alim in alimentadores_visiveis:
        if alim in camadas_ativas: mask_camadas = mask_camadas | ((df_mapa['ALIMENTADOR'] == alim) & (df_mapa['TIPO_REDE'].isin(camadas_ativas[alim])))
    df_mapa = df_mapa[mask_camadas]

    df_busca = pd.DataFrame()
    nearest_idx = None

    if busca_lat is not None and busca_lon is not None and not df_mapa.empty:
        pts, indices = [], []
        for idx, row in df_mapa.iterrows():
            if row['TIPO_GEOMETRIA'] == 'Ponto':
                pts.append(latlon_to_xyz(row['COORDS'][0], row['COORDS'][1]))
                indices.append(idx)
            else:
                for pt in row['COORDS']:
                    pts.append(latlon_to_xyz(pt[0], pt[1]))
                    indices.append(idx)
                    
        if pts:
            tree = cKDTree(pts)
            target_xyz = latlon_to_xyz(busca_lat, busca_lon)
            dist_3d, min_idx_in_pts = tree.query(target_xyz)
            nearest_idx = indices[min_idx_in_pts]
            
            elem_prox = df_mapa.loc[nearest_idx]
            if elem_prox['TIPO_GEOMETRIA'] == 'Ponto': dist_metros = haversine(busca_lat, busca_lon, elem_prox['COORDS'][0], elem_prox['COORDS'][1]) * 1000
            else: dist_metros = min([haversine(busca_lat, busca_lon, pt[0], pt[1]) for pt in elem_prox['COORDS']]) * 1000
            
            st.sidebar.success(f"🎯 **Alvo mais próximo:** {elem_prox['TIPO_REDE']} ({elem_prox['NOME']}) a {dist_metros:.1f} metros.")
            df_busca = df_mapa.loc[[nearest_idx]]
            df_mapa = df_mapa.drop(nearest_idx)

    elif termo_pesquisa != "":
        mask_nome = df_mapa['NOME'].astype(str).str.contains(termo_pesquisa, case=False, na=False)
        df_busca = df_mapa[mask_nome]
        df_mapa = df_mapa[~mask_nome]

    features = []
    for _, row in df_mapa.iterrows():
        coord_txt = f"{row['COORDS'][0]:.5f}, {row['COORDS'][1]:.5f}" if row['TIPO_GEOMETRIA'] == 'Ponto' else "Linha de Múltiplos Pontos"
        prop = {
            "TIPO_REDE": str(row['TIPO_REDE']), "NOME": str(row['NOME']), "ALIMENTADOR": str(row['ALIMENTADOR']),
            "MUNICIPIO": f"{row['MUNICIPIO']} - {row['REGIONAL']}", "GPS": coord_txt, "COR": row['COR']
        }
        
        if row['TIPO_GEOMETRIA'] == 'Linha':
            coords = [[pt[1], pt[0]] for pt in row['COORDS']]
            geom = {"type": "LineString", "coordinates": coords}
            for pt in row['COORDS']: todas_lats.append(pt[0]); todas_lons.append(pt[1])
        else:
            coords = [row['COORDS'][1], row['COORDS'][0]]
            geom = {"type": "Point", "coordinates": coords}
            todas_lats.append(row['COORDS'][0]); todas_lons.append(row['COORDS'][1])
            
        features.append({"type": "Feature", "geometry": geom, "properties": prop})

    if features:
        geojson_data = {"type": "FeatureCollection", "features": features}
        def style_fn(feature):
            cor = feature['properties']['COR']
            tipo = feature['properties']['TIPO_REDE']
            if feature['geometry']['type'] == 'LineString': return {'color': cor, 'weight': 4 if 'PRIM' in tipo else 3, 'opacity': 0.8}
            else: 
                raio = 6
                if 'POSTE' in tipo: raio = 6
                elif any(x in tipo for x in ['TRANSFORMADOR', 'CHAVE', 'REGULADOR', 'RELIGADOR', 'SUBESTA', 'CAPACITOR']): raio = 12
                return {'color': cor, 'fillColor': cor, 'fillOpacity': 1.0, 'radius': raio, 'weight': 2}

        folium.GeoJson(geojson_data, name="Rede Elétrica", style_function=style_fn, marker=folium.CircleMarker(radius=6, fill=True, fillOpacity=1), tooltip=folium.features.GeoJsonTooltip(fields=['TIPO_REDE', 'NOME'], aliases=['Rede:', 'Identificação:'], style="background-color: white; color: #333; font-family: arial; font-size: 12px; padding: 5px;"), popup=folium.features.GeoJsonPopup(fields=['TIPO_REDE', 'NOME', 'ALIMENTADOR', 'MUNICIPIO', 'GPS'], aliases=['Rede:', 'Identificação:', 'Alimentador:', 'Localização:', 'Coordenadas:'], style="font-family: sans-serif; font-size: 13px; min-width: 250px;")).add_to(mapa)

    fg_busca = folium.FeatureGroup(name="Resultado da Pesquisa", show=True)
    for _, row in df_busca.iterrows():
        coord_txt = f"{row['COORDS'][0]:.5f}, {row['COORDS'][1]:.5f}" if row['TIPO_GEOMETRIA'] == 'Ponto' else "Linha de Múltiplos Pontos"
        html_popup = f"""
        <div style="min-width: 250px; font-family: sans-serif;">
            <h4 style="margin-top: 0; color: #FF00FF; border-bottom: 2px solid #FF00FF; padding-bottom: 5px;">{row['TIPO_REDE']}</h4>
            <table style="width:100%;">
                <tr><td style="color: #555; padding: 2px;"><b>IDENTIFICAÇÃO:</b></td><td>{html.escape(str(row['NOME']))}</td></tr>
                <tr><td style="color: #555; padding: 2px;"><b>ALIMENTADOR:</b></td><td>{html.escape(str(row['ALIMENTADOR']))}</td></tr>
                <tr><td style="color: #555; padding: 2px;"><b>LOCAL:</b></td><td>{html.escape(str(row['MUNICIPIO']))} - {row['REGIONAL']}</td></tr>
                <tr><td style="color: #555; padding: 2px;"><b>GPS:</b></td><td>{coord_txt}</td></tr>
            </table>
        </div>
        """
        popup = folium.Popup(html_popup, max_width=350)
        if row['TIPO_GEOMETRIA'] == 'Linha':
            folium.PolyLine(locations=row['COORDS'], color='#FF00FF', weight=8, opacity=1.0, popup=popup, tooltip=f"ALVO ENCONTRADO: {html.escape(str(row['NOME']))}").add_to(fg_busca)
            for pt in row['COORDS']: busca_lats.append(pt[0]); busca_lons.append(pt[1])
        else:
            folium.Marker(location=row['COORDS'], icon=folium.Icon(color='purple', icon='star'), popup=popup, tooltip=f"ALVO ENCONTRADO: {html.escape(str(row['NOME']))}").add_to(fg_busca)
            busca_lats.append(row['COORDS'][0]); busca_lons.append(row['COORDS'][1])
    if busca_lat is not None and busca_lon is not None: folium.Marker(location=[busca_lat, busca_lon], icon=folium.Icon(color='orange', icon='map-pin', prefix='fa'), tooltip="Sua Pesquisa GPS").add_to(fg_busca)
    fg_busca.add_to(mapa)

if mostrar_quilombos:
    geo_q = get_kml_cached("assets/quilombos.kml", "#ff7f00")
    if geo_q: folium.GeoJson(geo_q, name="Áreas Quilombolas", style_function=lambda x: {'fillColor': x['properties']['COR'], 'color': x['properties']['COR'], 'weight': 2, 'fillOpacity': 0.4}).add_to(mapa)

if mostrar_indigenas:
    geo_i = get_kml_cached("assets/indigenas.kml", "#2ca02c")
    if geo_i: folium.GeoJson(geo_i, name="Terras Indígenas", style_function=lambda x: {'fillColor': x['properties']['COR'], 'color': x['properties']['COR'], 'weight': 2, 'fillOpacity': 0.4}).add_to(mapa)


# ==========================================
# CAMADAS DE OBRAS OTIMIZADAS (50 METROS)
# ==========================================
dados_tabela_conflito = []

if (mostrar_concluidas or mostrar_conflitantes or mostrar_heatmap) and msg_obras == "OK":
    
    # 🔥 Novo: Mapa de Calor (Densidade)
    if mostrar_heatmap:
        heat_data = []
        if df_andamento is not None and not df_andamento.empty: heat_data.extend(df_andamento[['LAT_CLEAN', 'LON_CLEAN']].values.tolist())
        if df_concluidas is not None and not df_concluidas.empty: heat_data.extend(df_concluidas[['LAT_CLEAN', 'LON_CLEAN']].values.tolist())
        if heat_data: HeatMap(heat_data, radius=15, blur=10, name="🔥 Densidade de Obras").add_to(mapa)
    
    protocolos_com_conflito = set()
    if df_andamento is not None:
        protocolos_com_conflito = set(df_andamento[df_andamento['CONFLITO']]['PROTOCOLO_CONFLITO'].astype(str))
    
    # 1. Desenha Obras Concluídas
    if mostrar_concluidas and df_concluidas is not None:
        fg_concluidas = folium.FeatureGroup(name="Obras Concluídas (Alvos)", show=True)
        for _, row in df_concluidas.iterrows():
            protocolo = str(row.get('PROTOCOLO', 'S/N'))
            if protocolo not in protocolos_com_conflito: continue

            lat, lon = row['LAT_CLEAN'], row['LON_CLEAN']
            municipio = str(row.get('MUNICIPIO', 'S/N'))
            cor_concluida = '#1f77b4' # Azul
            
            html_popup = f"""<div style="min-width: 200px; font-family: sans-serif;"><h4 style="margin-top: 0; color: {cor_concluida}; border-bottom: 2px solid {cor_concluida}; padding-bottom: 5px;">Obra Concluída</h4><table style="width:100%;"><tr><td style="color: #555; padding: 2px;"><b>PROTOCOLO:</b></td><td>{html.escape(protocolo)}</td></tr><tr><td style="color: #555; padding: 2px;"><b>MUNICÍPIO:</b></td><td>{html.escape(municipio)}</td></tr></table></div>"""
            folium.CircleMarker(location=[lat, lon], radius=4, color='black', weight=1, fill=True, fillColor=cor_concluida, fillOpacity=1).add_to(fg_concluidas)
            # RAIO REDUZIDO PARA 50 METROS AQUI
            folium.Circle(location=[lat, lon], radius=50, color=cor_concluida, weight=2, fill=True, fillColor=cor_concluida, fillOpacity=0.25, tooltip=f"Obra Concluída: {html.escape(protocolo)}", popup=folium.Popup(html_popup, max_width=300)).add_to(fg_concluidas)
        fg_concluidas.add_to(mapa)
            
    # 2. Desenha Obras em Andamento (Apenas Vermelhas/Conflitantes)
    if mostrar_conflitantes and df_andamento is not None:
        fg_andamento = folium.FeatureGroup(name="Obras Conflitantes", show=True)
        
        for _, row in df_andamento.iterrows():
            if not row['CONFLITO']: continue
                
            lat, lon = row['LAT_CLEAN'], row['LON_CLEAN']
            protocolo = str(row.get('PROTOCOLO', 'S/N'))
            status_list = str(row.get('STATUS LIST', 'S/N'))
            cor_ponto = 'red'
            titulo = "🚨 CONFLITO DETECTADO"
            info_extra = f"<tr><td style='color: red; padding: 2px;'><b>CONFLITO COM:</b></td><td style='color: red;'>{html.escape(row['PROTOCOLO_CONFLITO'])} ({row['DISTANCIA_CONFLITO']:.1f}m)</td></tr>"
            
            dados_tabela_conflito.append({
                "Protocolo (Nova)": protocolo,
                "Status (Nova)": status_list,
                "Conflito (Alvo Concluída)": row['PROTOCOLO_CONFLITO'],
                "Distância do Centro (m)": f"{row['DISTANCIA_CONFLITO']:.1f}m",
                "Latitude": lat,
                "Longitude": lon,
                "Google Maps": f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            })
                
            html_popup = f"""<div style="min-width: 250px; font-family: sans-serif;"><h4 style="margin-top: 0; color: {cor_ponto}; border-bottom: 2px solid {cor_ponto}; padding-bottom: 5px;">{titulo}</h4><table style="width:100%;"><tr><td style="color: #555; padding: 2px;"><b>PROTOCOLO:</b></td><td>{html.escape(protocolo)}</td></tr><tr><td style="color: #555; padding: 2px;"><b>STATUS:</b></td><td>{html.escape(status_list)}</td></tr>{info_extra}</table></div>"""
            folium.CircleMarker(location=[lat, lon], radius=6, color='black', weight=1, fill=True, fillColor=cor_ponto, fillOpacity=0.9, tooltip=f"{titulo}: {html.escape(protocolo)}", popup=folium.Popup(html_popup, max_width=300)).add_to(fg_andamento)
        fg_andamento.add_to(mapa)

folium.LayerControl(position='topright').add_to(mapa)

# ==========================================
# ⚡ CRUZAMENTO COM A MALHA (.KMZ)
# ==========================================
# Identifica qual Poste/Trafo está perto do conflito para colocar na tabela
if len(dados_tabela_conflito) > 0 and not df.empty:
    df_malha_filtro = df.copy()
    if alimentadores_visiveis: df_malha_filtro = df_malha_filtro[df_malha_filtro['ALIMENTADOR'].isin(alimentadores_visiveis)]
    if not df_malha_filtro.empty:
        grid_pts = []
        grid_info = []
        for idx, row in df_malha_filtro.iterrows():
            if row['TIPO_GEOMETRIA'] == 'Ponto':
                lat_m, lon_m = row['COORDS'][0], row['COORDS'][1]
                grid_pts.append(latlon_to_xyz(lat_m, lon_m))
                grid_info.append(f"{row['TIPO_REDE']} ({row['NOME']})")
            else:
                for pt in row['COORDS']:
                    lat_m, lon_m = pt[0], pt[1]
                    grid_pts.append(latlon_to_xyz(lat_m, lon_m))
                    grid_info.append(f"{row['TIPO_REDE']} ({row['NOME']})")
        if grid_pts:
            tree_grid = cKDTree(grid_pts)
            for conflito in dados_tabela_conflito:
                xyz = latlon_to_xyz(conflito['Latitude'], conflito['Longitude'])
                _, idx_prox = tree_grid.query(xyz)
                conflito['Rede Visível Próxima'] = grid_info[idx_prox]


# -------------------------------------------------------------
# 5. TABELA INTELIGENTE E BOTÃO DE EXPORTAÇÃO
# -------------------------------------------------------------
zoom_lat, zoom_lon = None, None

with table_container:
    if mostrar_conflitantes and msg_obras == "OK" and len(dados_tabela_conflito) > 0:
        st.markdown("---")
        st.markdown(f"<h3 style='color: #d62728;'>🚨 Relatório de Obras Sobrepostas (Total: {len(dados_tabela_conflito)})</h3>", unsafe_allow_html=True)
        st.markdown("As obras abaixo estão em andamento ou correção, mas a coordenada registrada encontra-se dentro do **raio de 50 metros** de uma obra já dada como concluída no SISCO.<br>💡 **DICA INTERATIVA:** Clique em qualquer linha da tabela abaixo para que o mapa foque e dê zoom exato na obra!", unsafe_allow_html=True)
        
        df_tabela = pd.DataFrame(dados_tabela_conflito)
        
        try:
            event = st.dataframe(
                df_tabela, 
                use_container_width=True, 
                on_select="rerun", 
                selection_mode="single_row",
                column_config={"Google Maps": st.column_config.LinkColumn("📍 Google Maps", display_text="Abrir Rota Google")}
            )
            if hasattr(event, 'selection') and event.selection.rows:
                idx = event.selection.rows[0]
                zoom_lat = float(df_tabela.iloc[idx]['Latitude'])
                zoom_lon = float(df_tabela.iloc[idx]['Longitude'])
        except Exception:
            st.dataframe(df_tabela, use_container_width=True)
        
        # 📥 BOTÃO NATIVO DE EXPORTAÇÃO EXCEL/CSV
        csv = df_tabela.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 Baixar Relatório Completo de Conflitos (CSV)",
            data=csv,
            file_name="conflitos_obras_mapeadas.csv",
            mime="text/csv",
            type="primary"
        )

# -------------------------------------------------------------
# 6. GERENCIAMENTO DE ZOOM E RENDERIZAÇÃO FINAL DO MAPA
# -------------------------------------------------------------
if zoom_lat is not None and zoom_lon is not None:
    mapa.fit_bounds([[zoom_lat - 0.001, zoom_lon - 0.001], [zoom_lat + 0.001, zoom_lon + 0.001]])
elif busca_lat is not None and busca_lon is not None:
    mapa.fit_bounds([[busca_lat - 0.001, busca_lon - 0.001], [busca_lat + 0.001, busca_lon + 0.001]])
elif busca_lats and busca_lons: 
    mapa.fit_bounds([[min(busca_lats), min(busca_lons)], [max(busca_lats), max(busca_lons)]])
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
    if mun_foco_lats and mun_foco_lons: mapa.fit_bounds([[min(mun_foco_lats), min(mun_foco_lons)], [max(mun_foco_lats), max(mun_foco_lons)]])
    elif todas_lats and todas_lons: mapa.fit_bounds([[min(todas_lats), min(todas_lons)], [max(todas_lats), max(todas_lons)]])
elif todas_lats and todas_lons: 
    mapa.fit_bounds([[min(todas_lats), min(todas_lons)], [max(todas_lats), max(todas_lons)]])

with map_container:
    st_folium(mapa, use_container_width=True, height=850, returned_objects=[])
