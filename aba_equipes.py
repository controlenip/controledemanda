import streamlit as st
import database

def render_equipes():
    st.subheader("👥 Gestão de Equipes de Campo")
    st.write("Adicione, edite ou remova equipes usando a tabela abaixo. As alterações vão direto para o Lançador.")
    
    df_equipes = database.ler_equipes_df()
    
    # Editor de dados interativo nativo do Streamlit (Permite adicionar/excluir linhas)
    df_editado = st.data_editor(
        df_equipes,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "EQUIPE": st.column_config.TextColumn("Nome da Equipe (Ex: EQUIPE 01)"),
            "COLABORADOR": st.column_config.TextColumn("Nome do Colaborador")
        }
    )
    
    # Botão para salvar alterações na tabela
    if st.button("💾 Salvar Alterações de Equipes", type="primary"):
        database.salvar_equipes_df(df_editado)
        st.success("✅ Equipes atualizadas com sucesso! Os novos nomes já estão no Lançador.")
