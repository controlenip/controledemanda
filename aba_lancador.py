import streamlit as st
import pandas as pd
import os
import database

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
    
    # --- INTEGRAÇÃO DIRETA COM A BASE DE OBRAS PARA BUSCA DA NOTA CCS ---
    notas_ccs_disponiveis = []
    if os.path.exists("data_2.xlsx"):
        try:
            df_obras = pd.read_excel("data_2.xlsx")
            # Procura pela coluna Nota CCS, se o nome for diferente, tenta usar a 1ª coluna
            col_ccs = "Nota CCS" if "Nota CCS" in df_obras.columns else df_obras.columns[0]
            
            # Limpa notações científicas e transforma tudo em lista de texto para a pesquisa funcionar
            valores_ccs = pd.to_numeric(df_obras[col_ccs], errors='coerce').fillna(0).astype('Int64').astype(str)
            valores_ccs = valores_ccs[valores_ccs != "0"]
            notas_ccs_disponiveis = valores_ccs.unique().tolist()
        except:
            pass
            
    # --- LÓGICA CONDICIONAL DE CAMPOS (Habilita ao informar Obras >= 1) ---
    if qtd_obras > 0:
        st.info("💡 Campos adicionais habilitados! Digite os números na caixa abaixo para buscar as obras.")
        
        # CAIXA DE PESQUISA (MULTI-SELECT)
        obras_selecionadas = st.multiselect(
            "NOTA CCS (Selecione uma ou mais obras):", 
            options=notas_ccs_disponiveis,
            help="Comece a digitar o número para filtrar a lista. Você pode escolher várias."
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
        
    # BOTÃO DE SALVAMENTO COM AS EXATAS COLUNAS EXIGIDAS
    if st.button("💾 SALVAR PRODUÇÃO DIÁRIA", type="primary", use_container_width=True):
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
