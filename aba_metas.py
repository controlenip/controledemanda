import streamlit as st
import pandas as pd
import os
import datetime

def render_metas():
    st.subheader("🎯 Obras e Metas Preditivas & ETA")
    
    arquivo_dados = "Produtividade_Levantadores_NIP.xlsx"
    arquivo_base = "data_2.xlsx" if os.path.exists("data_2.xlsx") else "data.xlsx"
    
    if not os.path.exists(arquivo_dados):
        st.warning("⚠️ O arquivo de produtividade ainda não foi criado.")
        return
        
    try:
        df = pd.read_excel(arquivo_dados)
        if df.empty:
            st.info("A base de produtividade está vazia.")
            return
            
        df['DATA_LEVANTAMENTO'] = pd.to_datetime(df['DATA_LEVANTAMENTO'], format='%d/%m/%Y', errors='coerce')
        df['MesAno'] = df['DATA_LEVANTAMENTO'].dt.strftime('%m/%Y')
        meses_disponiveis = sorted(df['MesAno'].dropna().unique(), reverse=True)
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            mes_selecionado = st.selectbox("📅 Selecione o Mês de Referência:", meses_disponiveis)
        with col_m2:
            metrica_tipo = st.radio("Métrica de Análise:", ["Obras (Meta: 3.5/dia)", "Postes (PGS)"], horizontal=True)
            
        df_mes = df[df['MesAno'] == mes_selecionado].copy()
        
        # --- CÁLCULO DE ETA (PREVISÃO DE TÉRMINO DO LOTE) ---
        if os.path.exists(arquivo_base):
            df_base = pd.read_excel(arquivo_base)
            col_lev = next((c for c in df_base.columns if "LEVANTADOR" in str(c).upper()), "LEVANTADOR")
            if col_lev in df_base.columns:
                obras_pendentes = df_base[df_base[col_lev].isna() | (df_base[col_lev] == "")].shape[0]
            else:
                obras_pendentes = len(df_base)
                
            total_obras_mes = df_mes['Quantidade Obras'].sum()
            dias_trabalhados_geral = df_mes['DATA_LEVANTAMENTO'].nunique()
            ritmo_diario_equipe = total_obras_mes / dias_trabalhados_geral if dias_trabalhados_geral > 0 else 1
            
            if ritmo_diario_equipe > 0:
                dias_restantes_estimados = int(obras_pendentes / ritmo_diario_equipe)
                data_conclusao_estimada = datetime.date.today() + datetime.timedelta(days=dias_restantes_estimados)
                
                st.info(f"⏳ **Previsão de Término do Lote (ETA):** Restam **{obras_pendentes} obras** pendentes na base. No ritmo atual da equipe (**{ritmo_diario_equipe:.1f} obras/dia**), a previsão de conclusão é para **{data_conclusao_estimada.strftime('%d/%m/%Y')}** (~{dias_restantes_estimados} dias úteis).")
        
        st.divider()
        st.write(f"### 🚦 Gestão à Vista - Desempenho ({mes_selecionado})")
        
        target_val = 3.5 if "Obras" in metrica_tipo else 15.0
        col_agregada = 'Quantidade Obras' if "Obras" in metrica_tipo else 'PGS'
        
        resumo = df_mes.groupby('Levantador').agg(
            Total_Prod=(col_agregada, 'sum'),
            Dias_Trabalhados=('DATA_LEVANTAMENTO', 'nunique')
        ).reset_index()
        
        resumo['Media_Diaria'] = resumo['Total_Prod'] / resumo['Dias_Trabalhados']
        resumo['Projecao_Mensal'] = resumo['Media_Diaria'] * 21
        
        cols = st.columns(3)
        for i, row in resumo.iterrows():
            with cols[i % 3]:
                st.markdown(f"**👨‍💻 {row['Levantador']}**")
                media = row['Media_Diaria']
                
                if "Obras" in metrica_tipo:
                    status = "🟢 Ritmo Excelente" if media >= 3.5 else ("🟡 Ritmo de Atenção" if media >= 3.0 else "🔴 Ritmo de Alerta")
                else:
                    status = "🟢 Ritmo Alto" if media >= 12 else "🟡 Ritmo Regular"
                
                st.metric(
                    label="Média Diária", 
                    value=f"{media:.1f}", 
                    delta=f"{media - target_val:.1f} vs Meta",
                    delta_color="normal"
                )
                
                st.caption(f"{status}")
                st.write(f"**Total Acumulado:** {int(row['Total_Prod'])}")
                st.write(f"**Projeção Fim do Mês:** ~{int(row['Projecao_Mensal'])}")
                st.divider()
                
    except Exception as e:
        st.error(f"Erro ao carregar metas: {e}")
