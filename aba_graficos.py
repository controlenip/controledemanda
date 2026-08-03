import streamlit as st
import pandas as pd
import plotly.express as px
import os

def render_graficos():
    st.subheader("📈 Gráficos Analíticos de Produção")
    
    arquivo_dados = "Produtividade_Levantadores_NIP.xlsx"
    
    if not os.path.exists(arquivo_dados):
        st.warning("⚠️ O arquivo de produtividade ainda não existe.")
        return
        
    try:
        df = pd.read_excel(arquivo_dados)
        if df.empty:
            st.info("A base de produtividade está vazia.")
            return
            
        df['DATA_LEVANTAMENTO'] = pd.to_datetime(df['DATA_LEVANTAMENTO'], format='%d/%m/%Y', errors='coerce')
        
        c_sup1, c_sup2 = st.columns(2)
        with c_sup1:
            dias_filtro = st.slider("Visualizar últimos (dias):", min_value=7, max_value=90, value=30, step=7)
        with c_sup2:
            tipo_metrica = st.radio("Métrica dos Gráficos:", ["Obras Realizadas", "Postes (PGS)"], horizontal=True)
            
        col_metrica = 'Quantidade Obras' if tipo_metrica == "Obras Realizadas" else 'PGS'
        
        data_corte = pd.Timestamp.now().normalize() - pd.Timedelta(days=dias_filtro)
        df_filtrado = df[df['DATA_LEVANTAMENTO'] >= data_corte].copy()
        
        if df_filtrado.empty:
            st.warning("Nenhum dado encontrado para o período selecionado.")
            return

        st.write(f"### 📊 Produção Diária ({tipo_metrica})")
        prod_diaria = df_filtrado.groupby(['DATA_LEVANTAMENTO', 'Levantador'])[col_metrica].sum().reset_index()
        
        fig_bar = px.bar(
            prod_diaria, x='DATA_LEVANTAMENTO', y=col_metrica, color='Levantador',
            barmode='group', title=f"Evolução Diária por {tipo_metrica}",
            labels={'DATA_LEVANTAMENTO': 'Data', col_metrica: tipo_metrica}
        )
        if tipo_metrica == "Obras Realizadas":
            fig_bar.add_hline(y=3.5, line_dash="dash", line_color="red", annotation_text="Meta (3.5)")
        st.plotly_chart(fig_bar, use_container_width=True)
        
        st.divider()

        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### 🚧 Ofensor de Produtividade")
            st.caption("Motivos informados em dias com baixa produção")
            df_abaixo = df_filtrado[(df_filtrado['Quantidade Obras'] < 3) & (df_filtrado['Justificativa'] != 'Nenhuma (Dia Normal)')]
            
            if not df_abaixo.empty:
                just_counts = df_abaixo['Justificativa'].value_counts().reset_index()
                just_counts.columns = ['Justificativa', 'Ocorrências']
                fig_pie = px.pie(just_counts, values='Ocorrências', names='Justificativa', hole=0.4,
                                 color_discrete_sequence=px.colors.sequential.RdBu)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.success("🎉 Nenhuma justificativa de baixa produção registrada!")

        with col2:
            st.write("### 🔥 Média por Dia da Semana")
            dias_traducao = {
                'Monday': '1. Segunda', 'Tuesday': '2. Terça', 'Wednesday': '3. Quarta',
                'Thursday': '4. Quinta', 'Friday': '5. Sexta', 'Saturday': '6. Sábado', 'Sunday': '7. Domingo'
            }
            df_filtrado['Dia_Semana'] = df_filtrado['DATA_LEVANTAMENTO'].dt.day_name().map(dias_traducao)
            heatmap_data = df_filtrado.groupby(['Levantador', 'Dia_Semana'])[col_metrica].mean().reset_index()
            
            if not heatmap_data.empty:
                fig_heat = px.density_heatmap(
                    heatmap_data, x='Dia_Semana', y='Levantador', z=col_metrica,
                    color_continuous_scale="RdYlGn", 
                    labels={'Dia_Semana': 'Dia da Semana', col_metrica: f'Média {tipo_metrica}'}
                )
                st.plotly_chart(fig_heat, use_container_width=True)
            else:
                st.info("Dados insuficientes.")
                
    except Exception as e:
        st.error(f"Erro ao gerar gráficos: {e}")
