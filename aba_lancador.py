import streamlit as st
from datetime import datetime
import database

def render_lancador():
    st.header("📝 Formulário de Lançamento Diário")
    st.write("Preencha os dados da obra finalizada abaixo:")

    # Criação do formulário no Streamlit
    with st.form(key="form_lancador", clear_on_submit=True):
        colaborador = st.text_input("Colaborador:")
        nota_ccs = st.text_input("Nota CCS:")
        qtd_postes = st.number_input("Qtd Postes (PGS):", min_value=0, step=1)

        # Colocando KM Inicial e Final lado a lado
        col1, col2 = st.columns(2)
        with col1:
            km_inicial = st.number_input("KM Inicial:", min_value=0.0, step=0.1)
        with col2:
            km_final = st.number_input("KM Final:", min_value=0.0, step=0.1)

        dias_trabalhados = st.number_input("Dias Trabalhados:", min_value=1, value=1, step=1)

        justificativas = ["", "Chuva/Clima", "Veículo Quebrado", "Atraso Logístico", "Trânsito Intenso", "Problema de Saúde", "Outros"]
        justificativa = st.selectbox("Justificativa (Opcional):", options=justificativas)

        # Botão de Salvar atrelado ao form
        submit_button = st.form_submit_button(label="SALVAR DADOS NO BANCO")

        if submit_button:
            if not colaborador or qtd_postes == 0:
                st.warning("⚠️ Preencha o nome do Colaborador e a Quantidade de Postes!")
            else:
                novo_dado = {
                    "Data": datetime.now().strftime("%d/%m/%Y"),
                    "Colaborador": colaborador,
                    "Nota CCS": nota_ccs,
                    "Qtd Postes": qtd_postes,
                    "KM Inicial": km_inicial,
                    "KM Final": km_final,
                    "Justificativa": justificativa,
                    "Dias Trabalhados": dias_trabalhados
                }
                
                try:
                    database.salvar_registro(novo_dado)
                    st.success("✅ Registro salvo com sucesso no Banco de Dados!")
                except Exception as e:
                    st.error(f"❌ Erro ao salvar: {e}")
