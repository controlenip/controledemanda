import streamlit as st
import pandas as pd
import os
import database

# --- INTELIGÊNCIA DE BUSCA (CACHE) ---
@st.cache_data
def carregar_notas_ccs():
    arquivo = "data_2.xlsx" if os.path.exists("data_2.xlsx") else "data.xlsx"
    if os.path.exists(arquivo):
        try:
            df_obras = pd.read_excel(arquivo)
            col_ccs = "Nota CCS" if "Nota CCS" in df_obras.columns else df_obras.columns[0]
            valores_ccs = pd.to_numeric(df_obras[col_ccs], errors='coerce').dropna().astype('Int64').astype(str)
            return valores_ccs.unique().tolist()
        except Exception as e:
            st.error(f"Erro interno ao ler as Notas CCS: {e}")
            return []
    return []

def render_lancador():
    st.subheader("📝 Lançamento Manual Inteligente")
    
    # 1. MENSAGEM DE SUCESSO (Aparece após a tela ser limpa)
    if "msg_sucesso" in st.session_state:
        st.success(st.session_state.msg_sucesso)
        del st.session_state.msg_sucesso # Apaga para não ficar aparecendo para sempre

    # Entradas de Controle Base
    data_lancamento = st.date_input("Data do Levantamento:", format="DD/MM/YYYY")
    lista_equipes = database.get_lista_levantadores()
    
    if not lista_equipes:
        st.error("Nenhuma equipe cadastrada no sistema. Vá na aba de Gestão de Equipes.")
        return
        
    # A chave "key" é o que permite limpar a memória depois
    levantador = st.selectbox("Selecione a Equipe/Levantador:", options=lista_equipes, key="levantador_input")
    st.divider()
    
    # O gatilho principal
    qtd_obras = st.number_input("Quantidade de Obras Realizadas no Dia:", min_value=0, step=1, key="qtd_obras_input")
    
    nota_ccs_texto, pgs, km_inicial, km_final, status_lev = "", 0, 0, 0, ""
    
    notas_ccs_disponiveis = carregar_notas_ccs()
    
    # --- LÓGICA CONDICIONAL DE CAMPOS ---
    if qtd_obras > 0:
        st.info("💡 Campos adicionais habilitados! Digite os números na caixa abaixo para buscar as obras.")
        
        if not notas_ccs_disponiveis:
            st.warning("⚠️ O arquivo da Base de Obras não foi encontrado ou está vazio. Usando campo manual:")
            nota_ccs_texto = st.text_input("NOTA CCS (Digite manualmente):", key="nota_ccs_manual")
        else:
            obras_selecionadas = st.multiselect(
                "NOTA CCS (Pesquise e Selecione as obras):", 
                options=notas_ccs_disponiveis,
                help="Comece a digitar o número para filtrar a lista.",
                key="nota_ccs_multi"
            )
            nota_ccs_texto = ", ".join(obras_selecionadas)
        
        # --- LINHA 1: KMs JUNTOS E SEM CASA DECIMAL ---
        col1, col2 = st.columns(2)
        with col1:
            km_inicial = st.number_input("KM INICIAL:", min_value=0, step=1, key="km_ini_input")
        with col2:
            km_final = st.number_input("KM FINAL:", min_value=0, step=1, key="km_fin_input")
            
        # --- LINHA 2: STATUS E PGS ---
        col3, col4 = st.columns(2)
        with col3:
            status_lev = st.radio("Status do Levantamento:", ["LEVANTAMENTO FINALIZADO", "LEVANTAMENTO EM ANDAMENTO"], key="status_lev_input")
        with col4:
            pgs = st.number_input("PGS (Postes Levantados):", min_value=0, step=1, key="pgs_input")
            
    st.divider()
    
    # --- JUSTIFICATIVAS ---
    st.write("### ⚠️ Ocorrências e Impedimentos")
    justificativas_lista = [
        "Nenhuma (Dia Normal)", "Chuva/Clima", "Veículo Quebrado", 
        "Atraso Logístico (Combustível, OnFly)", "Retrabalho", 
        "Problema Técnico", "Outros"
    ]
    justificativa = st.selectbox("Justificativa Padrão:", options=justificativas_lista, key="just_input")
    
    motivo_outros = ""
    if justificativa == "Outros":
        motivo_outros = st.text_input("Especifique o motivo detalhadamente:", key="outros_input")
        
    # --- BOTÃO DE SALVAR E RESETAR TELA ---
    if st.button("💾 SALVAR PRODUÇÃO DIÁRIA", type="primary", use_container_width=True):
        if qtd_obras > 0 and not nota_ccs_texto:
            st.error("⚠️ Por favor, selecione ou digite pelo menos uma Nota CCS antes de salvar.")
            return
            
        novo_dado = {
            "DATA_LEVANTAMENTO": data_lancamento.strftime("%d/%m/%Y"),
            "Levantador": levantador,
            "Quantidade Obras": qtd_obras,
            "Nota CCS": nota_ccs_texto,
            "PGS": pgs,
            "KM Inicial": km_inicial,
            "KM Final": km_final,
            "Status Levantamento": status_lev,
            "Justificativa": justificativa,
            "Motivo Outros": motivo_outros
        }
        database.salvar_registro(novo_dado)
        
        # 2. SALVA A MENSAGEM PARA ELA APARECER APÓS O "F5 AUTOMÁTICO"
        st.session_state.msg_sucesso = f"✅ Produção de [{qtd_obras}] obras salva para {levantador}!"
        
        # 3. ZERA A MEMÓRIA DOS CAMPOS
        st.session_state.qtd_obras_input = 0
        if "nota_ccs_multi" in st.session_state: st.session_state.nota_ccs_multi = []
        if "nota_ccs_manual" in st.session_state: st.session_state.nota_ccs_manual = ""
        if "km_ini_input" in st.session_state: st.session_state.km_ini_input = 0
        if "km_fin_input" in st.session_state: st.session_state.km_fin_input = 0
        if "pgs_input" in st.session_state: st.session_state.pgs_input = 0
        if "status_lev_input" in st.session_state: st.session_state.status_lev_input = "LEVANTAMENTO FINALIZADO"
        st.session_state.just_input = "Nenhuma (Dia Normal)"
        if "outros_input" in st.session_state: st.session_state.outros_input = ""
        
        # 4. FORÇA A PÁGINA A RECARREGAR (Igual apertar F5, mas instantâneo)
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()
