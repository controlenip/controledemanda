import streamlit as st
import pandas as pd
import os

def render_obras():
    st.subheader("🏗️ Painel Geral de Status das Obras (Base Dinâmica)")
    
    # ==========================================
    # PAINEL ADMINISTRATIVO (CARGA E LIMPEZA)
    # ==========================================
    with st.expander("⚙️ Painel Administrativo (Atualizar Base ou Apagar Obras)", expanded=False):
        
        col_carga, col_apagar = st.columns(2)
        
        # 1. FUNÇÃO DE DAR CARGA / SUBSTITUIR
        with col_carga:
            st.write("#### 📥 Carga de Nova Base")
            st.write("Substitui a base atual por uma planilha atualizada.")
            arquivo_carga = st.file_uploader("Faça o upload da planilha (Excel)", type=["xlsx", "xls"])
            
            if st.button("Aplicar Carga (Substituir)", type="primary") and arquivo_carga:
                try:
                    df_novo = pd.read_excel(arquivo_carga)
                    df_novo.to_excel("data_2.xlsx", index=False)
                    st.cache_data.clear() # Limpa a memória para o app inteiro reconhecer a nova base
                    st.success("✅ Base atualizada com sucesso! A página recarregará em instantes.")
                    if hasattr(st, "rerun"): st.rerun()
                    else: st.experimental_rerun()
                except Exception as e:
                    st.error(f"Erro ao carregar arquivo: {e}")
                    
        # 2. FUNÇÃO DE APAGAR TODA A BASE
        with col_apagar:
            st.write("#### 🗑️ Apagar Todas as Obras")
            st.write("Exclui completamente as obras do sistema.")
            senha_apagar = st.text_input("Senha de Autorização:", type="password")
            
            if st.button("🚨 APAGAR TODA A BASE"):
                if senha_apagar == "Tho35@602@09":
                    try:
                        if os.path.exists("data_2.xlsx"): os.remove("data_2.xlsx")
                        if os.path.exists("data.xlsx"): os.remove("data.xlsx")
                        st.cache_data.clear() # Limpa a memória para o apagão funcionar
                        st.success("✅ Base completamente apagada! A página recarregará em instantes.")
                        if hasattr(st, "rerun"): st.rerun()
                        else: st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Erro ao apagar arquivo: {e}")
                else:
                    st.error("⚠️ Senha incorreta! Acesso negado.")

    st.divider()

    # ==========================================
    # LEITURA E EXIBIÇÃO DO BANCO DE DADOS
    # ==========================================
    arquivo_base = "data_2.xlsx" if os.path.exists("data_2.xlsx") else "data.xlsx"
    
    if not os.path.exists(arquivo_base):
        st.warning("⚠️ Nenhuma base de obras encontrada no sistema. Use o 'Painel Administrativo' acima para fazer o upload da planilha inicial.")
        return
        
    try:
        df = pd.read_excel(arquivo_base)
        df.columns = [str(c).strip() for c in df.columns]
        
        st.write("### 🔍 Filtros de Busca Avançados")
        
        # Colunas dinâmicas para organizar perfeitamente os filtros
        c1, c2, c3, c4, c5 = st.columns(5)
        
        # 1. Filtro: Município (Múltipla Seleção)
        col_municipio = next((c for c in df.columns if "MUNICÍPIO" in c.upper() or "MUNICIPIO" in c.upper()), None)
        with c1:
            if col_municipio:
                opcoes_mun = sorted(list(df[col_municipio].dropna().astype(str).unique()))
                sel_mun = st.multiselect("🏙️ Município", opcoes_mun, placeholder="Todos")
            else: sel_mun = []

        # 2. Filtro: PAT (Múltipla Seleção)
        col_pat = next((c for c in df.columns if "PAT" == c.upper()), None)
        with c2:
            if col_pat:
                opcoes_pat = sorted(list(df[col_pat].dropna().astype(str).unique()))
                sel_pat = st.multiselect("🏷️ PAT", opcoes_pat, placeholder="Todos")
            else: sel_pat = []
                
        # 3. Filtro: Tipo de Projeto (PI) (Múltipla Seleção)
        col_tipo = next((c for c in df.columns if "TIPO DE PROJETO" in c.upper()), None)
        with c3:
            if col_tipo:
                opcoes_tipo = sorted(list(df[col_tipo].dropna().astype(str).unique()))
                sel_tipo = st.multiselect("📂 Tipo (PI)", opcoes_tipo, placeholder="Todos")
            else: sel_tipo = []
            
        # 4. Filtro: Regional (Múltipla Seleção)
        col_regional = next((c for c in df.columns if "REGIONAL" in c.upper()), None)
        with c4:
            if col_regional:
                opcoes_reg = sorted(list(df[col_regional].dropna().astype(str).unique()))
                sel_reg = st.multiselect("📍 Regional", opcoes_reg, placeholder="Todas")
            else: sel_reg = []
            
        # 5. Filtro: Levantador (Múltipla Seleção)
        col_levantador = next((c for c in df.columns if "LEVANTADOR" in c.upper()), None)
        with c5:
            if col_levantador:
                opcoes_lev = sorted(list(df[col_levantador].dropna().astype(str).unique()))
                sel_lev = st.multiselect("👨‍💻 Levantador", opcoes_lev, placeholder="Todos")
            else: sel_lev = []


        # --- APLICAÇÃO INTELIGENTE DOS FILTROS MÚLTIPLOS ---
        df_filtrado = df.copy()
        
        # Se a lista de seleção não estiver vazia, ele filtra. Se estiver vazia, ignora (mostra todos)
        if col_municipio and len(sel_mun) > 0: 
            df_filtrado = df_filtrado[df_filtrado[col_municipio].astype(str).isin(sel_mun)]
            
        if col_pat and len(sel_pat) > 0: 
            df_filtrado = df_filtrado[df_filtrado[col_pat].astype(str).isin(sel_pat)]
            
        if col_tipo and len(sel_tipo) > 0: 
            df_filtrado = df_filtrado[df_filtrado[col_tipo].astype(str).isin(sel_tipo)]
            
        if col_regional and len(sel_reg) > 0: 
            df_filtrado = df_filtrado[df_filtrado[col_regional].astype(str).isin(sel_reg)]
            
        if col_levantador and len(sel_lev) > 0: 
            df_filtrado = df_filtrado[df_filtrado[col_levantador].astype(str).isin(sel_lev)]
            
        st.divider()
        st.metric("📊 Total de Obras Encontradas (Com os filtros aplicados)", len(df_filtrado))
        
        st.write("### 🗃️ Banco de Obras Detalhado")
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"Erro ao processar a planilha '{arquivo_base}': {e}")
