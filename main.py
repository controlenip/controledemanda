import streamlit as st

st.set_page_config(page_title="Gestão NIP", layout="wide", page_icon="⚡")

# NOVO CSS PARA BLOQUEAR O ZOOM (Fullscreen) DA IMAGEM
st.markdown("""
    <style>
        [data-testid="StyledFullScreenButton"] { display: none !important; }
    </style>
""", unsafe_allow_html=True)

# Importação dos módulos (páginas)
from aba_lancador import render_lancador
from aba_metas import render_metas
from aba_graficos import render_graficos
from aba_equipes import render_equipes
from aba_obras import render_obras

# --- Configuração do Menu Lateral ---
with st.sidebar:
    st.image("LOGO_NIP.png", width=220)
    st.divider()
    
    st.title("📍 Menu de Navegação")
    menu = st.radio(
        "Selecione o módulo:",
        [
            "1. Lançamento Diário", 
            "2. Obras e Metas Preditivas", 
            "3. Gráficos de Produção",
            "4. Gestão de Equipes",
            "5. Status das Obras (Base)"
        ]
    )

st.header("Sistema de Inteligência e Produtividade | NIP")
st.divider()

# Controle de Exibição
if menu == "1. Lançamento Diário":
    render_lancador()
elif menu == "2. Obras e Metas Preditivas":
    render_metas()
elif menu == "3. Gráficos de Produção":
    render_graficos()
elif menu == "4. Gestão de Equipes":
    render_equipes()
elif menu == "5. Status das Obras (Base)":
    render_obras()
