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
        
        # Filtro de tempo geral para os gráficos
        dias_filtro = st.slider("Visualizar últimos (dias):", min_value=7, max_value=90, value=30, step=7)
        data_corte = pd.Timestamp.now().normalize() - pd.Timedelta(days=dias_filtro)
        df_filtrado = df[df['DATA_LEVANTAMENTO'] >= data_corte].copy()
        
        if df_filtrado.empty:
            st.warning("Nenhum dado encontrado para o período selecionado.")
            return

        # ==========================================
        # 1. GRÁFICO DE PRODUÇÃO DIÁRIA VS META
        # ==========================================
        st.write("### 📊 Produção Diária vs Benchmark de Meta")
        
        prod_diaria = df_filtrado.groupby(['DATA_LEVANTAMENTO', 'Levantador'])['Quantidade Obras'].sum().reset_index()
        
        fig_bar = px.bar(
            prod_diaria, x='DATA_LEVANTAMENTO', y='Quantidade Obras', color='Levantador',
            barmode='group', title="Obras Concluídas por Dia (Linha Vermelha = Meta 3.5)",
            labels={'DATA_LEVANTAMENTO': 'Data', 'Quantidade Obras': 'Obras Feitas'}
        )
        # Adiciona a Linha de Meta Horizontal
        fig_bar.add_hline(y=3.5, line_dash="dash", line_color="red", annotation_text="Meta (3.5)")
        st.plotly_chart(fig_bar, use_container_width=True)
        
        st.divider()

        # Criando duas colunas para os gráficos inferiores
        col1, col2 = st.columns(2)
        
        # ==========================================
        # 2. GRÁFICO DE PARETO (GARGALOS)
        # ==========================================
        with col1:
            st.write("### 🚧 Ofensores de Produtividade")
            st.caption("Motivos informados em dias com menos de 3 obras")
            
            # Filtra apenas os dias onde a produção foi menor que 3 e descarta os "Dias Normais"
            df_abaixo = df_filtrado[(df_filtrado['Quantidade Obras'] < 3) & (df_filtrado['Justificativa'] != 'Nenhuma (Dia Normal)')]
            
            if not df_abaixo.empty:
                just_counts = df_abaixo['Justificativa'].value_counts().reset_index()
                just_counts.columns = ['Justificativa', 'Ocorrências']
                
                fig_pie = px.pie(just_counts, values='Ocorrências', names='Justificativa', hole=0.4,
                                 color_discrete_sequence=px.colors.sequential.RdBu)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.success("🎉 Nenhuma justificativa de baixa produção registrada no período!")

        # ==========================================
        # 3. MAPA DE CALOR SEMANAL (HEATMAP)
        # ==========================================
        with col2:
            st.write("### 🔥 Média de Produção por Dia da Semana")
            st.caption("Identifique padrões de queda de produtividade (Verde = Bom, Vermelho = Ruim)")
            
            # Extrai o dia da semana em português
            dias_traducao = {
                'Monday': '1. Segunda', 'Tuesday': '2. Terça', 'Wednesday': '3. Quarta',
                'Thursday': '4. Quinta', 'Friday': '5. Sexta', 'Saturday': '6. Sábado', 'Sunday': '7. Domingo'
            }
            df_filtrado['Dia_Semana'] = df_filtrado['DATA_LEVANTAMENTO'].dt.day_name().map(dias_traducao)
            
            heatmap_data = df_filtrado.groupby(['Levantador', 'Dia_Semana'])['Quantidade Obras'].mean().reset_index()
            
            if not heatmap_data.empty:
                fig_heat = px.density_heatmap(
                    heatmap_data, x='Dia_Semana', y='Levantador', z='Quantidade Obras',
                    color_continuous_scale="RdYlGn", 
                    labels={'Dia_Semana': 'Dia da Semana', 'Quantidade Obras': 'Média de Obras'}
                )
                st.plotly_chart(fig_heat, use_container_width=True)
            else:
                st.info("Dados insuficientes para gerar o mapa de calor.")
                
    except Exception as e:
        st.error(f"Erro ao gerar gráficos: {e}")
