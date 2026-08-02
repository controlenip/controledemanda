import streamlit as st
import database
from datetime import datetime

def render_lancador():
    st.subheader("📝 Lançamento Manual de Obras")
    
    with st.form(key="form_lancador", clear_on_submit=True):
        data_lancamento = st.date_input("Data do Levantamento:", format="DD/MM/YYYY")
        
        # Puxa a lista dinâmica de equipes salvas
        lista_equipes = database.get_lista_levantadores()
        
        levantador = st.selectbox("Selecione a Equipe/Levantador:", options=lista_equipes)
        qtd_obras = st.number_input("Quantidade de Obras Realizadas no Dia:", min_value=0, step=1)
        justificativa = st.text_input("Observação (Opcional):")
        
        submit = st.form_submit_button("SALVAR PRODUÇÃO")
        
        if submit:
            if not lista_equipes:
                st.error("Nenhuma equipe cadastrada! Adicione equipes no menu de 'Gestão de Equipes'.")
            else:
                novo_dado = {
                    "Data": data_lancamento.strftime("%d/%m/%Y"),
                    "Levantador": levantador,
                    "Quantidade Obras": qtd_obras,
                    "Justificativa": justificativa
                }
                database.salvar_registro(novo_dado)
                st.success(f"✅ Produção de {qtd_obras} obras salva para {levantador}!")
