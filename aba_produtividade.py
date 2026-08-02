import streamlit as st
import database

def render_produtividade():
    st.header("📊 Banco de Dados (Equipe)")
    st.write("Visualização de todos os dados registrados.")

    try:
        df = database.ler_registros()

        if df.empty:
            st.info("Nenhum registro encontrado ainda. Preencha o Lançador Rápido.")
        else:
            # Inverte a ordem para os mais recentes ficarem no topo (opcional)
            df_exibicao = df.iloc[::-1].reset_index(drop=True)
            
            # Mostra a tabela interativa (permite ordenar, buscar e baixar CSV)
            st.dataframe(df_exibicao, use_container_width=True)

            # Cartões de Resumo Rápido
            st.divider()
            st.subheader("Resumo Global")
            col1, col2 = st.columns(2)
            with col1:
                total_postes = df["Qtd Postes"].sum()
                st.metric("Total de Postes Instalados", f"{total_postes} PGS")
            with col2:
                total_lancamentos = len(df)
                st.metric("Lançamentos Registrados", total_lancamentos)

    except Exception as e:
        st.error(f"Erro ao carregar o banco de dados: {e}")
