import streamlit as st
import pandas as pd
import os

def render_obras():
    st.subheader("🏗️ Painel Geral de Status das Obras (Base de Dados)")
    
    if not os.path.exists("data.xlsx"):
        st.warning("⚠️ O arquivo 'data.xlsx' não foi encontrado no servidor.")
        return
        
    try:
        # Lê os dados do arquivo Excel fornecido
        df = pd.read_excel("data.xlsx", sheet_name="Sheet1")
        
        # Filtros Dinâmicos no Topo
        st.write("### 🔍 Filtros de Busca")
        col1, col2 = st.columns(2)
        with col1:
            regionais = ["Todas"] + list(df['Regional'].dropna().unique())
            regional_sel = st.selectbox("Filtrar por Regional", regionais)
        with col2:
            status = ["Todos"] + list(df['Status Atual(Levantamento)'].dropna().unique())
            status_sel = st.selectbox("Filtrar por Status", status)
            
        # Aplicação dos Filtros
        df_filtrado = df.copy()
        if regional_sel != "Todas":
            df_filtrado = df_filtrado[df_filtrado['Regional'] == regional_sel]
        if status_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Status Atual(Levantamento)'] == status_sel]
            
        # Métricas de Resumo Rápido
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("Total de Obras (Filtro)", len(df_filtrado))
        
        # Conta a quantidade de cada status chave
        qtd_liberado = len(df_filtrado[df_filtrado['Status Atual(Levantamento)'] == 'Liberado para Levantamento'])
        qtd_pre_analise = len(df_filtrado[df_filtrado['Status Atual(Levantamento)'] == 'Pré Análise'])
        
        m2.metric("🟢 Liberadas p/ Levantamento", qtd_liberado)
        m3.metric("🟡 Em Pré Análise", qtd_pre_analise)
        
        # Tabela Visível Completa
        st.write("### 📊 Banco de Obras Detalhado")
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"Erro ao processar a planilha 'data.xlsx': {e}")
