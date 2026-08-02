import streamlit as st
import pandas as pd
import altair as alt
import database

def render_graficos():
    st.subheader("📊 Dashboards de Produção")
    df = database.ler_registros()
    
    if df.empty:
        st.info("Aguardando dados para gerar gráficos.")
        return
        
    # Prepara as colunas de tempo
    df['Mês'] = df['Data'].dt.to_period('M').astype(str)
    df['Semana'] = df['Data'].dt.isocalendar().week
    
    # Sub-abas nativas do Streamlit para organizar os gráficos
    tab1, tab2, tab3 = st.tabs(["🗓️ Diário", "📅 Semanal", "📆 Mensal"])
    
    with tab1:
        st.write("Evolução Diária com Linhas de Meta (3 e 4 Obras)")
        df_dia = df.groupby(['Data', 'Levantador'])['Quantidade Obras'].sum().reset_index()
        
        # Gráfico de Barras Principal
        grafico_barras = alt.Chart(df_dia).mark_bar().encode(
            x='Data:T', y='Quantidade Obras:Q', color='Levantador:N'
        )
        
        # Linhas Preditivas / Alvos
        linha_3 = alt.Chart(pd.DataFrame({'y': [3]})).mark_rule(color='red', strokeDash=[5,5]).encode(y='y:Q')
        linha_4 = alt.Chart(pd.DataFrame({'y': [4]})).mark_rule(color='green', strokeDash=[5,5]).encode(y='y:Q')
        
        st.altair_chart(grafico_barras + linha_3 + linha_4, use_container_width=True)

    with tab2:
        st.write("Acumulado por Semana do Ano")
        df_sem = df.groupby(['Semana', 'Levantador'])['Quantidade Obras'].sum().reset_index()
        graf_sem = alt.Chart(df_sem).mark_bar().encode(
            x='Semana:O', y='Quantidade Obras:Q', color='Levantador:N'
        )
        st.altair_chart(graf_sem, use_container_width=True)
        
    with tab3:
        st.write("Acumulado Mensal")
        df_mes = df.groupby(['Mês', 'Levantador'])['Quantidade Obras'].sum().reset_index()
        graf_mes = alt.Chart(df_mes).mark_bar().encode(
            x='Mês:N', y='Quantidade Obras:Q', color='Levantador:N'
        )
        st.altair_chart(graf_mes, use_container_width=True)
