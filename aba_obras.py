import streamlit as st
import pandas as pd
import os
import aba_auditoria  # Importando o módulo de auditoria criado anteriormente

def render_obras():
    # 1. EXIBE O RAIO-X DE AUDITORIA NO TOPO DA TELA (OPÇÃO B)
    aba_auditoria.render_auditoria()
    
    st.divider()
    
    # 2. EXIBE A BASE MESTRA GERAL COM FILTROS INTELIGENTES
    st.subheader("📊 Base Mestra de Obras (Consulta Geral)")
    
    arquivo_base = "data_2.xlsx" if os.path.exists("data_2.xlsx") else "data.xlsx"
    
    if not os.path.exists(arquivo_base):
        st.warning("⚠️ O arquivo de base (data_2.xlsx ou data.xlsx) não foi encontrado.")
        return
        
    try:
        df = pd.read_excel(arquivo_base)
        
        # Identifica dinamicamente a coluna de Status e CCS para os filtros
        col_ccs = next((c for c in df.columns if "NOTA CCS" in str(c).upper().replace("_", " ")), df.columns[0])
        col_status = next((c for c in df.columns if "STATUS_LIST" in c.upper() or "STATUS ATUAL" in c.upper()), None)
        
        # Criação dos Filtros de Pesquisa na tela
        col1, col2 = st.columns(2)
        with col1:
            pesquisa_ccs = st.text_input("🔍 Pesquisar por NOTA CCS específica:")
        with col2:
            if col_status:
                lista_status = ["Todos os Status"] + sorted([str(x) for x in df[col_status].dropna().unique()])
                filtro_status = st.selectbox("Filtro por Status da Obra:", lista_status)
            else:
                filtro_status = "Todos os Status"

        # Aplicando os filtros no DataFrame
        df_filtrado = df.copy()
        
        if pesquisa_ccs:
            # Filtra ignorando espaços ou letras maiúsculas/minúsculas
            df_filtrado = df_filtrado[df_filtrado[col_ccs].astype(str).str.contains(pesquisa_ccs.strip(), case=False, na=False)]
            
        if filtro_status != "Todos os Status" and col_status:
            df_filtrado = df_filtrado[df_filtrado[col_status].astype(str) == filtro_status]
            
        # Exibição do contador e da tabela interativa
        st.write(f"Mostrando **{len(df_filtrado):,}** de **{len(df):,}** obras cadastradas.".replace(",", "."))
        
        st.dataframe(
            df_filtrado, 
            use_container_width=True, 
            hide_index=True,
            height=600 # Define uma altura boa para visualização de muitos dados
        )
        
    except Exception as e:
        st.error(f"Erro ao carregar e exibir a base de obras: {e}")
