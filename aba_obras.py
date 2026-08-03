import streamlit as st
import pandas as pd
import os
import aba_auditoria

def render_obras():
    ARQUIVO_BASE = "data_2.xlsx"
    ARQUIVO_ALTERNATIVO = "data.xlsx"

    # Define qual arquivo está em uso
    arquivo_ativo = ARQUIVO_BASE if os.path.exists(ARQUIVO_BASE) else (ARQUIVO_ALTERNATIVO if os.path.exists(ARQUIVO_ALTERNATIVO) else None)

    st.subheader("⚙️ Gerenciamento e Status da Base Mestra")
    
    # ==========================================
    # 1. ZONA DE PERIGO: SOBRESCREVER OU APAGAR A BASE
    # ==========================================
    with st.expander("⚠️ Gerenciar Arquivo da Base Mestra (Sobrescrever / Apagar)", expanded=False):
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("**🔄 Sobrescrever Base Existente**")
            st.caption("Faça upload de uma nova planilha para substituir a atual.")
            novo_arquivo = st.file_uploader("Upload da Nova Base (.xlsx)", type=["xlsx"])
            
            if novo_arquivo:
                if st.button("🚀 Confirmar Substituição da Base", type="primary", use_container_width=True):
                    with open(ARQUIVO_BASE, "wb") as f:
                        f.write(novo_arquivo.getbuffer())
                    # Remove a data.xlsx antiga se existir para evitar conflitos
                    if os.path.exists(ARQUIVO_ALTERNATIVO) and ARQUIVO_BASE != ARQUIVO_ALTERNATIVO:
                        os.remove(ARQUIVO_ALTERNATIVO)
                    st.success("✅ Base atualizada com sucesso!")
                    if hasattr(st, "rerun"): st.rerun()
                    else: st.experimental_rerun()

        with c2:
            st.markdown("**🗑️ Apagar Base de Dados**")
            st.caption("Deleta o arquivo atual. O sistema ficará vazio até uma nova base ser enviada.")
            
            if arquivo_ativo:
                confirmar_exclusao = st.checkbox("Tenho certeza que desejo apagar a base atual.")
                if confirmar_exclusao:
                    if st.button("❌ APAGAR BASE DEFINITIVAMENTE", type="primary", use_container_width=True):
                        os.remove(arquivo_ativo)
                        st.success("✅ Base apagada. O sistema agora está limpo.")
                        if hasattr(st, "rerun"): st.rerun()
                        else: st.experimental_rerun()
            else:
                st.info("A base de dados já está vazia/inexistente.")

    st.divider()

    if not arquivo_ativo:
        st.warning("⚠️ Nenhuma base de obras encontrada. Use o painel acima para fazer o upload da planilha (data_2.xlsx).")
        return

    # ==========================================
    # 2. RAIO-X DE AUDITORIA (No topo da página)
    # ==========================================
    aba_auditoria.render_auditoria()
    st.divider()
    
    # ==========================================
    # 3. PAINEL DA BASE MESTRA E FILTROS COMPLETOS
    # ==========================================
    try:
        df = pd.read_excel(arquivo_ativo)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Identificação inteligente das colunas
        col_ccs = next((c for c in df.columns if "NOTA CCS" in str(c).upper().replace("_", " ")), df.columns[0])
        col_status = next((c for c in df.columns if "STATUS" in c.upper() and ("ATUAL" in c.upper() or "LIST" in c.upper())), None)
        col_mun = next((c for c in df.columns if "MUNIC" in c.upper()), None)
        col_equipe = next((c for c in df.columns if "LEVANTADOR" in c.upper() or "EQUIPE" in c.upper()), None)
        
        st.write("### 🔎 Filtros Avançados de Consulta")
        
        # Linha 1 de Filtros
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            pesquisa_ccs = st.text_input("🔍 Buscar por NOTA CCS (Parte do número):")
        with f_col2:
            if col_equipe and not df[col_equipe].empty:
                lista_equipe = ["Todas as Equipes"] + sorted([x for x in df[col_equipe].dropna().astype(str).unique() if x.strip() != ""])
                filtro_equipe = st.selectbox("👷 Filtrar por Equipe/Levantador:", lista_equipe)
            else:
                filtro_equipe = "Todas as Equipes"
        
        # Linha 2 de Filtros
        f_col3, f_col4 = st.columns(2)
        with f_col3:
            if col_status and not df[col_status].empty:
                lista_status = ["Todos os Status"] + sorted([x for x in df[col_status].dropna().astype(str).unique() if x.strip() != ""])
                filtro_status = st.selectbox("🚦 Filtrar por Status:", lista_status)
            else:
                filtro_status = "Todos os Status"
                
        with f_col4:
            if col_mun and not df[col_mun].empty:
                lista_mun = ["Todos os Municípios"] + sorted([x for x in df[col_mun].dropna().astype(str).unique() if x.strip() != ""])
                filtro_mun = st.selectbox("📍 Filtrar por Município:", lista_mun)
            else:
                filtro_mun = "Todos os Municípios"
                
        # --- APLICAÇÃO DOS FILTROS ---
        df_filtrado = df.copy()
        
        if pesquisa_ccs:
            df_filtrado = df_filtrado[df_filtrado[col_ccs].astype(str).str.contains(pesquisa_ccs.strip(), case=False, na=False)]
        if filtro_equipe != "Todas as Equipes" and col_equipe:
            df_filtrado = df_filtrado[df_filtrado[col_equipe].astype(str) == filtro_equipe]
        if filtro_status != "Todos os Status" and col_status:
            df_filtrado = df_filtrado[df_filtrado[col_status].astype(str) == filtro_status]
        if filtro_mun != "Todos os Municípios" and col_mun:
            df_filtrado = df_filtrado[df_filtrado[col_mun].astype(str) == filtro_mun]
            
        # --- EXIBIÇÃO DA TABELA E EXPORTAÇÃO ---
        st.write(f"Mostrando **{len(df_filtrado):,}** registros de um total de **{len(df):,}** obras na base.".replace(",", "."))
        
        st.dataframe(
            df_filtrado,
            use_container_width=True,
            hide_index=True,
            height=500 
        )
        
        csv_export = df_filtrado.to_csv(index=False, sep=";").encode('utf-8-sig')
        st.download_button(
            label="📥 Baixar Resultado do Filtro (CSV)",
            data=csv_export,
            file_name="Relatorio_Obras_Filtradas.csv",
            mime="text/csv",
            type="secondary"
        )
        
    except Exception as e:
        st.error(f"Erro ao ler a base de dados: {e}")
