import streamlit as st
from PIL import Image
import os

# Configuração Base (Deve ser o 1º comando Streamlit do script)
st.set_page_config(page_title="Gestão de Produtividade NIP", layout="wide", page_icon="⚡")

# Importação dos módulos que criamos
from aba_lancador import render_lancador
from aba_produtividade import render_produtividade

# --- Cabeçalho e Logo ---
col1, col2 = st.columns([1, 4])
with col1:
    try:
        logo = Image.open("LOGO_NIP.png")
        st.image(logo, use_column_width=True)
    except FileNotFoundError:
        st.write("**(LOGO NIP)**")
with col2:
    st.title("Sistema de Gestão de Produtividade")
    st.subheader("NIP | Grupo Igneo")

st.divider()

# --- Sistema de Navegação (Abas) ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📝 Lançador Rápido", 
    "📊 Produtividade", 
    "⚙️ Parâmetros", 
    "📈 Dashboard Executivo"
])

# Rendeziando o conteúdo de cada arquivo na sua respectiva aba
with tab1:
    render_lancador()

with tab2:
    render_produtividade()

with tab3:
    st.header("⚙️ Parâmetros")
    st.info("Aba de Configurações e Parâmetros em Desenvolvimento...")

with tab4:
    st.header("📈 Dashboard Executivo")
    st.info("Gráficos do Dashboard em Desenvolvimento...")
