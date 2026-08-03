import streamlit as st
import pandas as pd
import os
import datetime

def render_metas():
    st.subheader("🎯 Obras e Metas Preditivas")
    
    arquivo_dados = "Produtividade_Levantadores_NIP.xlsx"
    
    if not os.path.exists(arquivo_dados):
        st.warning("⚠️ O arquivo de produtividade ainda não foi criado. Faça um lançamento na aba Lançamento Diário primeiro.")
        return
        
    try:
        df = pd.read_excel(arquivo_dados)
        if df.empty:
            st.info("A base de produtividade está vazia.")
            return
            
        # Converte datas
        df['DATA_LEVANTAMENTO'] = pd.to_datetime(df['DATA_LEVANTAMENTO'], format='%d/%m/%Y', errors='coerce')
        
        # Cria coluna de Mês/Ano para filtrar
        df['MesAno'] = df['DATA_LEVANTAMENTO'].dt.strftime('%m/%Y')
        meses_disponiveis = sorted(df['MesAno'].dropna().unique(), reverse=True)
        
        mes_selecionado = st.selectbox("📅 Selecione o Mês de Referência:", meses_disponiveis)
        df_mes = df[df['MesAno'] == mes_selecionado].copy()
        
        st.divider()
        st.write(f"### 🚦 Gestão à Vista - Desempenho ({mes_selecionado})")
        st.write("*Meta Diária: 3.5 obras / Meta Mensal Estimada: ~73 obras (21 dias úteis)*")
        
        # Agrupa os dados por Levantador
        resumo = df_mes.groupby('Levantador').agg(
            Total_Obras=('Quantidade Obras', 'sum'),
            Dias_Trabalhados=('DATA_LEVANTAMENTO', 'nunique')
        ).reset_index()
        
        resumo['Media_Diaria'] = resumo['Total_Obras'] / resumo['Dias_Trabalhados']
        
        # Projeção de fim de mês baseada em 21 dias úteis
        dias_uteis_mes = 21
        resumo['Projecao_Mensal'] = resumo['Media_Diaria'] * dias_uteis_mes
        
        # Cria 3 colunas para organizar os cards lado a lado
        cols = st.columns(3)
        
        for i, row in resumo.iterrows():
            with cols[i % 3]:
                st.markdown(f"**👨‍💻 {row['Levantador']}**")
                media = row['Media_Diaria']
                
                # Lógica do Farol de Cores e Texto
                if media >= 3.5:
                    status = "🟢 Ritmo Excelente"
                elif media >= 3.0:
                    status = "🟡 Ritmo de Atenção"
                else:
                    status = "🔴 Ritmo de Alerta"
                
                st.metric(
                    label="Média Diária", 
                    value=f"{media:.1f} obras", 
                    delta=f"{media - 3.5:.1f} vs Meta (3.5)",
                    delta_color="normal"
                )
                
                st.caption(f"{status}")
                st.write(f"**Total Acumulado:** {row['Total_Obras']} obras")
                st.write(f"**Projeção Fim do Mês:** ~{int(row['Projecao_Mensal'])} obras")
                st.divider()
                
    except Exception as e:
        st.error(f"Erro ao carregar metas: {e}")
