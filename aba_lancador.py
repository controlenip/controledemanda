import streamlit as st
import database
from datetime import datetime

def render_lancador():
    st.subheader("📝 Lançamento Manual Dinâmico")
    
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
    
    # Variáveis padrão (vazias)
    nota_ccs, pgs, km_inicial, km_final, status_lev = "", 0, 0.0, 0.0, ""
    
    # --- LÓGICA CONDICIONAL DE CAMPOS ---
    if qtd_obras > 0:
        st.info("💡 Campos adicionais habilitados com base na produção informada.")
        col1, col2 = st.columns(2)
        with col1:
            nota_ccs = st.text_input("NOTA CCS:")
            km_inicial = st.number_input("KM INICIAL:", min_value=0.0, step=0.1)
        with col2:
            pgs = st.number_input("PGS (Postes Levantados):", min_value=0, step=1)
            km_final = st.number_input("KM FINAL:", min_value=0.0, step=0.1)
            
        status_lev = st.radio("Status do Levantamento:", ["LEVANTAMENTO FINALIZADO", "LEVANTAMENTO EM ANDAMENTO"])
    
    st.divider()
    
    # --- JUSTIFICATIVAS ---
    st.write("### ⚠️ Ocorrências e Impedimentos")
    justificativas_lista = [
        "Nenhuma (Dia Normal)",
        "Chuva/Clima", 
        "Veículo Quebrado", 
        "Atraso Logístico (Combustível, OnFly)", 
        "Retrabalho", 
        "Problema Técnico", 
        "Outros"
    ]
    justificativa = st.selectbox("Justificativa Padrão:", options=justificativas_lista)
    
    motivo_outros = ""
    if justificativa == "Outros":
        motivo_outros = st.text_input("Especifique o motivo detalhadamente:")
        
    # Botão de Salvar
    if st.button("💾 SALVAR PRODUÇÃO DIÁRIA", type="primary", use_container_width=True):
        novo_dado = {
            "Data": data_lancamento.strftime("%d/%m/%Y"),
            "Levantador": levantador,
            "Quantidade Obras": qtd_obras,
            "Nota CCS": nota_ccs,
            "PGS": pgs,
            "KM Inicial": km_inicial,
            "KM Final": km_final,
            "Status Levantamento": status_lev,
            "Justificativa": justificativa,
            "Motivo Outros": motivo_outros
        }
        database.salvar_registro(novo_dado)
        st.success(f"✅ Produção salva perfeitamente para {levantador} no dia {data_lancamento.strftime('%d/%m/%Y')}!")
