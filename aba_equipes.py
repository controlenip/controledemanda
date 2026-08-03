import streamlit as st
import pandas as pd
import os
import plotly.express as px
import io

def render_equipes():
    st.subheader("👥 Gestão de Equipes & Eficiência Logística")
    
    arquivo_dados = "Produtividade_Levantadores_NIP.xlsx"
    
    if not os.path.exists(arquivo_dados):
        st.warning("⚠️ O arquivo de produtividade ainda não foi criado. Faça lançamentos diários primeiro.")
        return
        
    try:
        df = pd.read_excel(arquivo_dados)
        if df.empty:
            st.info("A base de produtividade está vazia.")
            return
            
        df['DATA_LEVANTAMENTO'] = pd.to_datetime(df['DATA_LEVANTAMENTO'], format='%d/%m/%Y', errors='coerce')
        
        # Cálculo de KM rodado por registro (KM Final - KM Inicial)
        df['KM_Rodado'] = df['KM Final'] - df['KM Inicial']
        df['KM_Rodado'] = df['KM_Rodado'].apply(lambda x: x if x > 0 else 0)
        
        # ==========================================
        # 1. MÓDULO DE EFICIÊNCIA LOGÍSTICA (KM)
        # ==========================================
        st.write("### 🚗 Painel de Eficiência Logística (Análise de Quilometragem)")
        st.caption("Cruzamento de quilômetros rodados e consumo de deslocamento por obra entregue.")
        
        df_log = df.groupby('Levantador').agg(
            Total_Obras=('Quantidade Obras', 'sum'),
            Total_KM=('KM_Rodado', 'sum'),
            Dias_Trabalhados=('DATA_LEVANTAMENTO', 'nunique')
        ).reset_index()
        
        df_log['KM_Por_Obra'] = df_log.apply(lambda r: r['Total_KM'] / r['Total_Obras'] if r['Total_Obras'] > 0 else 0, axis=1)
        
        col_l1, col_l2, col_l3 = st.columns(3)
        with col_l1:
            st.metric("Total de KM Rodados", f"{int(df_log['Total_KM'].sum()):,} km".replace(',', '.'))
        with col_l2:
            st.metric("Total de Obras Registradas", int(df_log['Total_Obras'].sum()))
        with col_l3:
            media_geral_km = df_log['Total_KM'].sum() / df_log['Total_Obras'].sum() if df_log['Total_Obras'].sum() > 0 else 0
            st.metric("Média Geral KM / Obra", f"{media_geral_km:.1f} km/obra")
            
        st.dataframe(df_log[['Levantador', 'Total_Obras', 'Total_KM', 'KM_Por_Obra']].style.format({
            'Total_KM': '{:,.0f}',
            'KM_Por_Obra': '{:.1f} km'
        }), use_container_width=True, hide_index=True)
        
        st.divider()
        
        # ==========================================
        # 2. PERFIL INDIVIDUAL DO COLABORADOR (DRILL-DOWN)
        # ==========================================
        st.write("### 👤 Dossiê e Perfil Individual do Colaborador")
        st.caption("Selecione um levantador para analisar o histórico detalhado de produtividade e ocorrências.")
        
        lista_levantadores = sorted(df['Levantador'].dropna().unique().tolist())
        if lista_levantadores:
            levantador_selecionado = st.selectbox("Selecione o Levantador:", lista_levantadores)
            
            df_ind = df[df['Levantador'] == levantador_selecionado].sort_values('DATA_LEVANTAMENTO')
            
            if not df_ind.empty:
                c1, c2, c3, c4 = st.columns(4)
                tot_obras_ind = df_ind['Quantidade Obras'].sum()
                tot_km_ind = df_ind['KM_Rodado'].sum()
                dias_ind = df_ind['DATA_LEVANTAMENTO'].nunique()
                media_ind = tot_obras_ind / dias_ind if dias_ind > 0 else 0
                
                with c1: st.metric("Total Obras (Indiv.)", tot_obras_ind)
                with c2: st.metric("Média Diária", f"{media_ind:.1f}")
                with c3: st.metric("Total KM Rodados", f"{int(tot_km_ind)} km")
                with c4: st.metric("Dias Trabalhados", dias_ind)
                
                # Gráfico de evolução individual
                fig_ind = px.line(
                    df_ind, x='DATA_LEVANTAMENTO', y='Quantidade Obras', markers=True,
                    title=f"Evolução de Produtividade Diária - {levantador_selecionado}",
                    labels={'DATA_LEVANTAMENTO': 'Data', 'Quantidade Obras': 'Obras Realizadas'}
                )
                fig_ind.add_hline(y=3.5, line_dash="dash", line_color="red", annotation_text="Meta (3.5)")
                st.plotly_chart(fig_ind, use_container_width=True)
                
                # Justificativas mais frequentes do colaborador
                st.write(f"**Histórico de Justificativas Registradas ({levantador_selecionado}):**")
                just_ind = df_ind['Justificativa'].value_counts().reset_index()
                just_ind.columns = ['Justificativa', 'Quantidade']
                st.dataframe(just_ind, use_container_width=True, hide_index=True)
        
        st.divider()
        
        # ==========================================
        # 3. EXPORTAÇÃO DE RELATÓRIOS EXECUTIVOS
        # ==========================================
        st.write("### 📤 Exportar Relatório Executivo")
        st.write("Baixe o fechamento completo da produtividade e o resumo logístico em um arquivo Excel profissional pronto para reuniões.")
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Produtividade_Completa', index=False)
            df_log.to_excel(writer, sheet_name='Resumo_Logistica_Equipes', index=False)
        output.seek(0)
        
        st.download_button(
            label="📥 Baixar Relatório Executivo em Excel (.xlsx)",
            data=output,
            file_name="Relatorio_Executivo_NIP.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )
        
    except Exception as e:
        st.error(f"Erro ao processar dados de equipes: {e}")
