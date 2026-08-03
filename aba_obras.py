import streamlit as st
import pandas as pd
import os
import aba_auditoria

def render_obras():
    # ==========================================
    # 1. RAIO-X DE AUDITORIA (No topo da página)
    # ==========================================
    aba_auditoria.render_auditoria()
    
    st.divider()
    
    # ==========================================
    # 2. PAINEL DA BASE MESTRA E FILTROS
    # ==========================================
    st.subheader("📊 Status das Obras (Base Mestra)")
    st.caption("Consulte, filtre e exporte o status atualizado de todas as obras do lote.")
    
    arquivo_base = "data_2.xlsx" if os.path.exists("data_2.xlsx") else "data.xlsx"
    
    if not os.path.exists(arquivo_base):
        st.warning("⚠️ O arquivo de base (data_2.xlsx ou data.xlsx) não foi encontrado no sistema.")
        return
        
    try:
        # Carregamento da base
        df = pd.read_excel(arquivo_base)
        
        # Limpa os nomes das colunas para evitar erros de espaços invisíveis
        df.columns = [str(c).strip() for c in df.columns]
        
        # Identificação inteligente das colunas essenciais
        col_ccs = next((c for c in df.columns if "NOTA CCS" in str(c).upper().replace("_", " ")), df.columns[0])
        col_status = next((c for c in df.columns if "STATUS" in c.upper() and ("ATUAL" in c.upper() or "LIST" in c.upper())), None)
        col_mun = next((c for c in df.columns if "MUNIC" in c.upper()), None)
        
        # --- ÁREA DE FILTROS INTERATIVOS ---
        st.write("### 🔎 Filtros de Pesquisa")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            pesquisa_ccs = st.text_input("Buscar por NOTA CCS (Digite o número):")
            
        with col2:
            if col_status and not df[col_status].empty:
                # Remove itens nulos, converte para string, ordena e cria a lista
                lista_status = ["Todos os Status"] + sorted([x for x in df[col_status].dropna().astype(str).unique() if x.strip() != ""])
                filtro_status = st.selectbox("Filtrar por Status:", lista_status)
            else:
                filtro_status = "Todos os Status"
                st.info("Coluna de Status não detectada.")
                
        with col3:
            if col_mun and not df[col_mun].empty:
                lista_mun = ["Todos os Municípios"] + sorted([x for x in df[col_mun].dropna().astype(str).unique() if x.strip() != ""])
                filtro_mun = st.selectbox("Filtrar por Município:", lista_mun)
            else:
                filtro_mun = "Todos os Municípios"
                
        # --- APLICAÇÃO DOS FILTROS NO DATAFRAME ---
        df_filtrado = df.copy()
        
        if pesquisa_ccs:
            # Busca aproximada ignorando maiúsculas e minúsculas
            df_filtrado = df_filtrado[df_filtrado[col_ccs].astype(str).str.contains(pesquisa_ccs.strip(), case=False, na=False)]
            
        if filtro_status != "Todos os Status" and col_status:
            df_filtrado = df_filtrado[df_filtrado[col_status].astype(str) == filtro_status]
            
        if filtro_mun != "Todos os Municípios" and col_mun:
            df_filtrado = df_filtrado[df_filtrado[col_mun].astype(str) == filtro_mun]
            
        # --- EXIBIÇÃO DA TABELA ---
        st.write(f"Mostrando **{len(df_filtrado):,}** registros de um total de **{len(df):,}** obras na base.".replace(",", "."))
        
        # Renderiza a tabela otimizada
        st.dataframe(
            df_filtrado,
            use_container_width=True,
            hide_index=True,
            height=500  # Mantém uma altura fixa confortável para rolar os dados
        )
        
        # --- BOTÃO DE EXPORTAÇÃO RÁPIDA ---
        st.write("### 📥 Download dos Dados")
        csv_export = df_filtrado.to_csv(index=False, sep=";").encode('utf-8-sig') # utf-8-sig garante que acentos fiquem corretos no Excel
        
        st.download_button(
            label="Baixar Tabela Filtrada (CSV)",
            data=csv_export,
            file_name="Status_Obras_Filtradas.csv",
            mime="text/csv",
            type="secondary"
        )
        
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar a base de obras: {e}")
