import streamlit as st
import pandas as pd
import os
import plotly.express as px
import io
import datetime

def render_equipes():
    st.subheader("👥 Gestão de Equipes & Relatório para WhatsApp")
    
    arquivo_dados = "Produtividade_Levantadores_NIP.xlsx"
    
    if not os.path.exists(arquivo_dados):
        st.warning("⚠️ O arquivo de produtividade ainda não foi criado.")
        return
        
    try:
        df = pd.read_excel(arquivo_dados)
        if df.empty:
            st.info("A base de produtividade está vazia.")
            return
            
        df['DATA_LEVANTAMENTO'] = pd.to_datetime(df['DATA_LEVANTAMENTO'], format='%d/%m/%Y', errors='coerce')
        df['KM_Rodado'] = (df['KM Final'] - df['KM Inicial']).apply(lambda x: x if x > 0 else 0)
        
        # ==========================================
        # 1. GERADOR DE RELATÓRIO RÁPIDO PARA WHATSAPP
        # ==========================================
        with st.expander("📱 Gerador de Relatório Rápido para WhatsApp", expanded=True):
            st.write("Gere um resumo formatado com emojis para enviar nos grupos da empresa em segundos.")
            
            data_zap = st.date_input("Data do Relatório:", value=datetime.date.today(), format="DD/MM/YYYY")
            df_zap = df[df['DATA_LEVANTAMENTO'].dt.date == data_zap]
            
            tot_obras_zap = int(df_zap['Quantidade Obras'].sum()) if not df_zap.empty else 0
            tot_pgs_zap = int(df_zap['PGS'].sum()) if not df_zap.empty else 0
            tot_km_zap = int(df_zap['KM_Rodado'].sum()) if not df_zap.empty else 0
            
            texto_whatsapp = f"""📊 *RESUMO DIÁRIO NIP - {data_zap.strftime('%d/%m/%Y')}*
✅ *Total de Obras Hoje:* {tot_obras_zap}
⚡ *Total de Postes (PGS):* {tot_pgs_zap}
🚗 *KM Total Rodado:* {tot_km_zap} km
👷‍♂️ *Equipes Ativas:* {df_zap['Levantador'].nunique() if not df_zap.empty else 0}
"""
            st.text_area("Copie o texto abaixo:", value=texto_whatsapp, height=150)
            st.info("💡 Dica: Selecione o texto acima e copie para colar diretamente no WhatsApp da equipe.")

        st.divider()

        # ==========================================
        # 2. MÓDULO DE EFICIÊNCIA LOGÍSTICA
        # ==========================================
        st.write("### 🚗 Eficiência Logística (Análise de Quilometragem)")
        df_log = df.groupby('Levantador').agg(
            Total_Obras=('Quantidade Obras', 'sum'),
            Total_KM=('KM_Rodado', 'sum'),
            Dias_Trabalhados=('DATA_LEVANTAMENTO', 'nunique')
        ).reset_index()
        
        df_log['KM_Por_Obra'] = df_log.apply(lambda r: r['Total_KM'] / r['Total_Obras'] if r['Total_Obras'] > 0 else 0, axis=1)
        
        col_l1, col_l2, col_l3 = st.columns(3)
        with col_l1: st.metric("Total KM Rodados", f"{int(df_log['Total_KM'].sum()):,} km".replace(',', '.'))
        with col_l2: st.metric("Total Obras", int(df_log['Total_Obras'].sum()))
        with col_l3: 
            media_geral_km = df_log['Total_KM'].sum() / df_log['Total_Obras'].sum() if df_log['Total_Obras'].sum() > 0 else 0
            st.metric("Média Geral KM/Obra", f"{media_geral_km:.1f} km")
            
        st.dataframe(df_log.style.format({'Total_KM': '{:,.0f}', 'KM_Por_Obra': '{:.1f} km'}), use_container_width=True, hide_index=True)
        st.divider()
        
        # ==========================================
        # 3. PERFIL INDIVIDUAL (DRILL-DOWN)
        # ==========================================
        st.write("### 👤 Dossiê do Colaborador")
        lista_levantadores = sorted(df['Levantador'].dropna().unique().tolist())
        if lista_levantadores:
            levantador_selecionado = st.selectbox("Selecione o Levantador:", lista_levantadores)
            df_ind = df[df['Levantador'] == levantador_selecionado].sort_values('DATA_LEVANTAMENTO')
            
            if not df_ind.empty:
                c1, c2, c3, c4 = st.columns(4)
                tot_ob = df_ind['Quantidade Obras'].sum()
                tot_km = df_ind['KM_Rodado'].sum()
                dias = df_ind['DATA_LEVANTAMENTO'].nunique()
                med = tot_ob / dias if dias > 0 else 0
                
                with c1: st.metric("Total Obras", tot_ob)
                with c2: st.metric("Média Diária", f"{med:.1f}")
                with c3: st.metric("Total KM", f"{int(tot_km)} km")
                with c4: st.metric("Dias Trab.", dias)
                
                fig_ind = px.line(df_ind, x='DATA_LEVANTAMENTO', y='Quantidade Obras', markers=True, title=f"Produtividade Diária - {levantador_selecionado}")
                fig_ind.add_hline(y=3.5, line_dash="dash", line_color="red", annotation_text="Meta (3.5)")
                st.plotly_chart(fig_ind, use_container_width=True)
        
        st.divider()
        
        # ==========================================
        # 4. EXPORTAÇÃO EXECUTIVA
        # ==========================================
        st.write("### 📤 Exportar Relatório Executivo")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Produtividade_Completa', index=False)
            df_log.to_excel(writer, sheet_name='Resumo_Logistica', index=False)
        output.seek(0)
        
        st.download_button(
            label="📥 Baixar Relatório Executivo (.xlsx)",
            data=output,
            file_name="Relatorio_Executivo_NIP.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )
        
    except Exception as e:
        st.error(f"Erro ao processar equipes: {e}")
