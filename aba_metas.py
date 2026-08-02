import streamlit as st
import pandas as pd
import datetime
import database

def render_metas():
    st.subheader("🎯 Acompanhamento Analítico e Preditivo")
    df = database.ler_registros()
    
    if df.empty:
        st.warning("Nenhum dado registrado ainda. Faça um lançamento na aba lateral.")
        return

    # 1. Variáveis de Tempo e Metas
    data_inicio = pd.to_datetime("2026-08-01")
    data_fim = pd.to_datetime("2026-12-31")
    hoje = pd.to_datetime(datetime.date.today())
    
    total_dias = (data_fim - data_inicio).days + 1  # 153 dias totais
    
    # Descobrindo quantos dias já se passaram
    if hoje < data_inicio: dias_corridos = 1
    elif hoje > data_fim: dias_corridos = total_dias
    else: dias_corridos = (hoje - data_inicio).days + 1

    dias_restantes = total_dias - dias_corridos
    if dias_restantes < 1: dias_restantes = 1
    
    # 2. Lógica de Cores Exigida
    def colorir_producao(valor):
        try:
            v = float(valor)
            if v < 3: return 'color: red; font-weight: bold;'
            elif 3 <= v <= 4: return 'color: blue; font-weight: bold;'
            else: return 'color: green; font-weight: bold;'
        except: return ''

    # 3. Tabela de Lançamentos Diários com Cores
    st.write("### 📋 Histórico Diário (Ajuste Visual Automático)")
    df_diario = df.copy()
    df_diario['Data'] = df_diario['Data'].dt.strftime('%d/%m/%Y')
    
    st.dataframe(
        df_diario.style.map(colorir_producao, subset=['Quantidade Obras']),
        use_container_width=True, hide_index=True
    )
    
    st.divider()

    # 4. Análise Preditiva e Estatística
    st.write("### 🤖 Previsão de Fechamento (Projeção)")
    
    # Agrupa os dados somando as obras por levantador
    df_stats = df.groupby('Levantador').agg(
        Total_Obras=('Quantidade Obras', 'sum'),
        Dias_Trabalhados=('Data', 'nunique') # Dias únicos trabalhados
    ).reset_index()
    
    # Realiza os cálculos estatísticos
    df_stats['Média Diária Atual'] = (df_stats['Total_Obras'] / dias_corridos).round(2)
    df_stats['Projeção Fim do Ano'] = (df_stats['Total_Obras'] + (df_stats['Média Diária Atual'] * dias_restantes)).astype(int)
    
    meta_total = total_dias * 3 # Considerando a base de 3 obras/dia
    df_stats['Meta Total da Campanha'] = meta_total
    
    df_stats['% Meta Atingida'] = ((df_stats['Total_Obras'] / meta_total) * 100).round(1).astype(str) + "%"
    df_stats['Faltam (Obras)'] = meta_total - df_stats['Total_Obras']
    df_stats.loc[df_stats['Faltam (Obras)'] < 0, 'Faltam (Obras)'] = 0 # Não deixa ficar negativo
    
    df_stats['Ritmo Necessário (Obras p/ Dia Restante)'] = (df_stats['Faltam (Obras)'] / dias_restantes).round(2)
    
    st.dataframe(df_stats, use_container_width=True, hide_index=True)
