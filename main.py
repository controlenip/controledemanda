import streamlit as st

st.set_page_config(page_title="Gestão NIP", layout="wide", page_icon="⚡")

# Código CSS para ocultar o botão de zoom (fullscreen) das imagens
st.markdown("""
    <style>
        button[title="View fullscreen"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# Importação dos módulos (páginas)
from aba_lancador import render_lancador
from aba_metas import render_metas
from aba_graficos import render_graficos

# --- Configuração do Menu Lateral ---
with st.sidebar:
    # A logo agora fica na lateral, dimensionada perfeitamente
    st.image("LOGO_NIP.png", width=220)
    st.divider()
    
    st.title("📍 Menu de Navegação")
    menu = st.radio(
        "Selecione o módulo:",
        ["1. Lançamento Diário", "2. Obras e Metas Preditivas", "3. Gráficos de Produção"]
    )

st.header("Análise Preditiva de Produtividade | NIP Grupo Igneo")

# Controle de Exibição
if menu == "1. Lançamento Diário":
    render_lancador()
elif menu == "2. Obras e Metas Preditivas":
    render_metas()
elif menu == "3. Gráficos de Produção":
    render_graficos()
