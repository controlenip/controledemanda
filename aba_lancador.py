import streamlit as st
import pandas as pd
import os
import database

# --- INTELIGÊNCIA DE BUSCA (CACHE) ---
# Isso faz o sistema carregar as obras uma única vez e deixar a digitação super rápida
@st.cache_data
def carregar_notas_ccs():
    # Procura pelo data_2.xlsx primeiro. Se não achar, usa o data.xlsx
    arquivo = "data_2.xlsx" if os.path.exists("data_2.xlsx") else "data.xlsx"
    
    if os.path.exists(arquivo):
        try:
            df_obras = pd.read_excel(arquivo)
            col_ccs = "Nota CCS" if "Nota CCS" in df_obras.columns else df_obras.columns[0]
            
            # Converte as notas (mesmo as em notação científica) para texto limpo e sem zeros flutuantes
            valores_ccs = pd.to_numeric(df_obras[col_ccs], errors='coerce').dropna().astype('Int64').astype(str)
            return valores_ccs.unique().tolist()
        except Exception as e:
            st.error(f"Erro interno ao ler as Notas CCS: {e}")
            return []
    return []

def render_lancador():
    st.subheader("📝 Lançamento Manual Inteligente")
    
    # Entradas de Controle Base
    data_lancamento = st.date_input("Data do Levantamento:", format="DD/MM/YYYY")
    lista_equipes = database.get_lista_levantadores()
    
    if not lista_equipes:
        st.error("Nenhuma equipe cadastrada no sistema. Vá na aba de Gestão de Equipes.")
        return
        
    levantador = st.selectbox("Selecione a Equipe/Levantador:", options=lista_equipes)
    st.divider()
    
    # O gatilho principal
    qtd_obras = st.number_input("Quantidade de Obras Realizadas no Dia:", min_value=0, step=1, value=0)
    
    nota_ccs_texto, pgs, km_inicial, km_final, status_lev = "", 0, 0.0, 0.0, ""
    
    # Puxa a lista inteligente do cache
    notas_ccs_disponiveis = carregar_notas_ccs()
    
    # --- LÓGICA CONDICIONAL DE CAMPOS ---
    if qtd_obras > 0:
        st.info("💡 Campos adicionais habilitados! Digite os números na caixa abaixo para buscar as obras.")
        
        # VERIFICAÇÃO SE A PLANILHA FOI ENCONTRADA
        if not notas_ccs_disponiveis:
            st.warning("⚠️ O arquivo da Base de Obras não foi encontrado ou está vazio. Usando campo manual:")
            nota_ccs_texto = st.text_input("NOTA CCS (Digite manualmente):")
        else:
            # A CAIXA DE SELEÇÃO MÚLTIPLA E FILTRO
            obras_selecionadas = st.multiselect(
                "NOTA CCS (Pesquise e Selecione as obras):", 
                options=notas_ccs_disponiveis,
                help="Comece a digitar o número para filtrar a lista. Selecione uma por vez até completar as obras do dia."
            )
            nota_ccs_texto = ", ".join(obras_selecionadas)
        
        col1, col2 = st.columns(2)
        with col1:
            km_inicial = st.number_input("KM INICIAL:", min_value=0.0, step=0.1)
            status_lev = st.radio("Status do Levantamento:", ["LEVANTAMENTO FINALIZADO", "LEVANTAMENTO EM ANDAMENTO"])
        with col2:
            pgs = st.number_input("PGS (Postes Levantados):", min_value=0, step=1)
            km_final = st.number_input("KM FINAL:", min_value=0.0, step=0.1)
            
    st.divider()
    
    # --- JUSTIFICATIVAS ---
    st.write("### ⚠️ Ocorrências e Impedimentos")
    justificativas_lista = [
        "Nenhuma (Dia Normal)", "Chuva/Clima", "Veículo Quebrado", 
        "Atraso Logístico (Combustível, OnFly)", "Retrabalho", 
        "Problema Técnico", "Outros"
    ]
    justificativa = st.selectbox("Justificativa Padrão:", options=justificativas_lista)
    
    motivo_outros = ""
    if justificativa == "Outros":
        motivo_outros = st.text_input("Especifique o motivo detalhadamente:")
        
    # BOTÃO DE SALVAR
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
        st.success(f"✅ Produção com PGS [{pgs}] salva perfeitamente para {levantador}!")
