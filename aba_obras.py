import streamlit as st
import pandas as pd
import os

def render_obras():
    st.subheader("🏗️ Painel Geral de Status das Obras (Base Dinâmica)")
    
    # Busca o arquivo de dados mais recente
    arquivo_base = "data_2.xlsx" if os.path.exists("data_2.xlsx") else "data.xlsx"
    
    if not os.path.exists(arquivo_base):
        st.warning(f"⚠️ O arquivo '{arquivo_base}' não foi encontrado no servidor. Faça o upload dele no GitHub.")
        return
        
    try:
        df = pd.read_excel(arquivo_base)
        
        # Limpa espaços vazios nos nomes das colunas para evitar erros de leitura
        df.columns = [str(c).strip() for c in df.columns]
        
        st.write("### 🔍 Filtros de Busca Avançados")
        
        # Cria 4 colunas na tela para organizar os filtros lado a lado
        col1, col2, col3, col4 = st.columns(4)
        
        # 1. Filtro: LEVANTADOR
        # Busca automaticamente a coluna que contenha "LEVANTADOR" no nome
        col_levantador = next((c for c in df.columns if "LEVANTADOR" in c.upper()), None)
        with col1:
            if col_levantador:
                opcoes_lev = ["Todos"] + sorted(list(df[col_levantador].dropna().astype(str).unique()))
                sel_lev = st.selectbox("👨‍💻 Levantador", opcoes_lev)
            else:
                sel_lev = "Todos"
                st.selectbox("👨‍💻 Levantador", ["Todos"], disabled=True, help="Coluna não encontrada na base.")
                
        # 2. Filtro: TIPO DE PROJETO (PI)
        col_tipo = next((c for c in df.columns if "TIPO DE PROJETO" in c.upper()), None)
        with col2:
            if col_tipo:
                opcoes_tipo = ["Todos"] + sorted(list(df[col_tipo].dropna().astype(str).unique()))
                sel_tipo = st.selectbox("📂 Tipo de Projeto (PI)", opcoes_tipo)
            else:
                sel_tipo = "Todos"
                st.selectbox("📂 Tipo de Projeto (PI)", ["Todos"], disabled=True)
        
        # 3. Filtro: REGIONAL
        col_regional = next((c for c in df.columns if "REGIONAL" in c.upper()), None)
        with col3:
            if col_regional:
                opcoes_reg = ["Todas"] + sorted(list(df[col_regional].dropna().astype(str).unique()))
                sel_reg = st.selectbox("📍 Regional", opcoes_reg)
            else:
                sel_reg = "Todas"
                st.selectbox("📍 Regional", ["Todas"], disabled=True)
                
        # 4. Filtro: MUNICÍPIO
        col_municipio = next((c for c in df.columns if "MUNICÍPIO" in c.upper() or "MUNICIPIO" in c.upper()), None)
        with col4:
            if col_municipio:
                opcoes_mun = ["Todos"] + sorted(list(df[col_municipio].dropna().astype(str).unique()))
                sel_mun = st.selectbox("🏙️ Município", opcoes_mun)
            else:
                sel_mun = "Todos"
                st.selectbox("🏙️ Município", ["Todos"], disabled=True, help="Coluna de Município não encontrada na base atual.")

        # --- APLICAÇÃO DOS FILTROS ---
        df_filtrado = df.copy()
        
        if col_levantador and sel_lev != "Todos":
            df_filtrado = df_filtrado[df_filtrado[col_levantador].astype(str) == sel_lev]
            
        if col_tipo and sel_tipo != "Todos":
            df_filtrado = df_filtrado[df_filtrado[col_tipo].astype(str) == sel_tipo]
            
        if col_regional and sel_reg != "Todas":
            df_filtrado = df_filtrado[df_filtrado[col_regional].astype(str) == sel_reg]
            
        if col_municipio and sel_mun != "Todos":
            df_filtrado = df_filtrado[df_filtrado[col_municipio].astype(str) == sel_mun]
            
        # Métricas de Resumo
        st.divider()
        st.metric("📊 Total de Obras Encontradas (Com os filtros acima)", len(df_filtrado))
        
        # Renderização da Nova Planilha Completa
        st.write("### 🗃️ Banco de Obras Detalhado")
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"Erro ao processar a planilha '{arquivo_base}': {e}")
