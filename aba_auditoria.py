import streamlit as st
import pandas as pd
import os

def render_auditoria():
    st.subheader("🔍 Raio-X de Inconsistências (Auditoria da Base Mestra)")
    st.caption("Varredura automática em busca de erros operacionais e obras esquecidas na base que podem travar o faturamento.")
    
    arquivo_base = "data_2.xlsx" if os.path.exists("data_2.xlsx") else "data.xlsx"
    
    if not os.path.exists(arquivo_base):
        st.warning("⚠️ Base de obras (data_2.xlsx ou data.xlsx) não encontrada no sistema.")
        return
        
    try:
        df = pd.read_excel(arquivo_base)
        
        # Identificação inteligente das colunas
        col_ccs = next((c for c in df.columns if "NOTA CCS" in str(c).upper().replace("_", " ")), df.columns[0])
        col_mun = next((c for c in df.columns if "MUNIC" in c.upper()), None)
        col_inst = next((c for c in df.columns if "INSTALA" in c.upper() or "CONTRATO" in c.upper()), None)
        col_status = next((c for c in df.columns if "STATUS_LIST" in c.upper() or "STATUS ATUAL" in c.upper()), None)
        col_nome = next((c for c in df.columns if "NOME" in c.upper()), None)
        
        c1, c2, c3 = st.columns(3)
        
        # 1. Alerta: Sem Município / Localização Falha
        if col_mun:
            df_sem_mun = df[df[col_mun].isna() | (df[col_mun].astype(str).str.strip() == "") | (df[col_mun].astype(str) == "0") | (df[col_mun].astype(str).str.lower() == "none")]
            with c1:
                st.metric("🚨 Obras Sem Município", len(df_sem_mun))
                if not df_sem_mun.empty:
                    with st.expander("Ver Lista (Necessário Correção)"):
                        st.dataframe(df_sem_mun[[col_ccs, col_mun] + ([col_nome] if col_nome else [])].head(100), hide_index=True)
        else:
            with c1: st.info("Coluna de Município não detectada.")

        # 2. Alerta: Sem Instalação / Conta Contrato
        if col_inst:
            df_sem_inst = df[df[col_inst].isna() | (df[col_inst].astype(str).str.strip() == "") | (df[col_inst].astype(str) == "0") | (df[col_inst].astype(str).str.lower() == "none")]
            with c2:
                st.metric("⚠️ Sem Nº Conta/Instalação", len(df_sem_inst))
                if not df_sem_inst.empty:
                    with st.expander("Ver Lista (Sem Vínculo)"):
                        st.dataframe(df_sem_inst[[col_ccs, col_inst] + ([col_nome] if col_nome else [])].head(100), hide_index=True)
        else:
            with c2: st.info("Coluna de Instalação não detectada.")

        # 3. Alerta: Obras Travadas em "Em Levantamento"
        if col_status:
            df_travadas = df[df[col_status].astype(str).str.contains("Em levantamento|Andamento", case=False, na=False)]
            with c3:
                st.metric("⏳ Travadas 'Em Levantamento'", len(df_travadas))
                if not df_travadas.empty:
                    with st.expander("Ver Lista (Verificar Gargalo)"):
                        st.dataframe(df_travadas[[col_ccs, col_status] + ([col_nome] if col_nome else [])].head(100), hide_index=True)
        else:
            with c3: st.info("Coluna de Status não detectada.")
            
        st.divider()
        st.success(f"✅ Varredura concluída. Total de obras na base mestra processadas: {len(df):,}".replace(",", "."))
        
    except Exception as e:
        st.error(f"Erro ao processar a auditoria da base: {e}")
