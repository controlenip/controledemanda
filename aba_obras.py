import streamlit as st
import pandas as pd
import os

def render_obras():
    st.subheader("🏗️ Painel Geral de Status das Obras (Base Dinâmica)")
    
    arquivo_base = "data_2.xlsx"
    
    if not os.path.exists(arquivo_base):
        st.warning(f"⚠️ O arquivo '{arquivo_base}' não foi encontrado no servidor. Faça o upload dele no GitHub.")
        return
        
    try:
        df = pd.read_excel(arquivo_base)
        
        # Filtros Dinâmicos (Procura inteligentemente pelas colunas que existirem no novo arquivo)
        st.write("### 🔍 Filtros de Busca")
        
        colunas_disponiveis = df.columns.tolist()
        
        # Identifica colunas para usar de filtro (Prioriza Regional e Status)
        col_f1 = "Regional" if "Regional" in colunas_disponiveis else colunas_disponiveis[0]
        col_f2 = "Status Atual(Levantamento)" if "Status Atual(Levantamento)" in colunas_disponiveis else (colunas_disponiveis[1] if len(colunas_disponiveis) > 1 else colunas_disponiveis[0])
        
        col1, col2 = st.columns(2)
        with col1:
            opcoes_1 = ["Todas"] + list(df[col_f1].dropna().unique())
            sel_1 = st.selectbox(f"Filtrar por {col_f1}", opcoes_1)
        with col2:
            opcoes_2 = ["Todos"] + list(df[col_f2].dropna().unique())
            sel_2 = st.selectbox(f"Filtrar por {col_f2}", opcoes_2)
            
        # Aplicação dos Filtros
        df_filtrado = df.copy()
        if sel_1 != "Todas":
            df_filtrado = df_filtrado[df_filtrado[col_f1] == sel_1]
        if sel_2 != "Todos":
            df_filtrado = df_filtrado[df_filtrado[col_f2] == sel_2]
            
        # Métricas de Resumo
        st.divider()
        st.metric("📊 Total de Obras (Abaixo)", len(df_filtrado))
        
        # Renderização da Nova Planilha Completa
        st.write("### 🗃️ Banco de Obras Detalhado (Layout Novo)")
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"Erro ao processar a planilha '{arquivo_base}': {e}")
