import streamlit as st
import pandas as pd
import datetime
import altair as alt
import database

def render_metas():
    # Estilo CSS para os cartões parecerem com o dashboard da diretoria
    st.markdown("""
        <style>
        .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; text-align: center; border-left: 5px solid #1C2A59; }
        .metric-value { font-size: 24px; font-weight: bold; color: #1C2A59; }
        .metric-label { font-size: 14px; color: #555; }
        </style>
    """, unsafe_allow_html=True)

    st.subheader("📊 Painel de Produtividade e Previsibilidade (Diretoria)")
    df = database.ler_registros()
    lista_equipes = database.get_lista_levantadores()
    
    # 1. PARÂMETROS E MATEMÁTICA DO PROJETO
    META_DIARIA = 3.5
    data_inicio = pd.to_datetime("2026-08-01")
    data_fim = pd.to_datetime("2026-12-31")
    hoje = pd.to_datetime(datetime.date.today())
    
    # Cálculo inteligente: Apenas os Dias Úteis (Seg-Sex)
    data_ref = min(hoje, data_fim) 
    if data_ref < data_inicio:
        dias_uteis_corridos = 0
    else:
        dias_uteis_corridos = len(pd.bdate_range(data_inicio, data_ref))
        
    meta_acumulada_indiv = dias_uteis_corridos * META_DIARIA
    
    # Separação das equipes
    titulares = [e for e in lista_equipes if "APOIO" not in e.upper()]
    apoios = [e for e in lista_equipes if "APOIO" in e.upper()]
    
    # Metas Acumuladas
    meta_geral = len(lista_equipes) * meta_acumulada_indiv
    meta_titulares = len(titulares) * meta_acumulada_indiv
    meta_apoio = len(apoios) * meta_acumulada_indiv
    
    # Realizado (Se não houver dados, assume 0)
    if not df.empty:
        realizado_geral = df['Quantidade Obras'].sum()
        df_titulares = df[df['Levantador'].isin(titulares)]
        realizado_titulares = df_titulares['Quantidade Obras'].sum()
        df_apoio = df[df['Levantador'].isin(apoios)]
        realizado_apoio = df_apoio['Quantidade Obras'].sum()
    else:
        realizado_geral = realizado_titulares = realizado_apoio = 0

    # 2. CARTÕES DE INDICADORES (KPIs)
    def render_kpi(label_realizado, val_realizado, label_meta, val_meta):
        atingimento = (val_realizado / val_meta * 100) if val_meta > 0 else 0
        cor = "green" if atingimento >= 100 else ("orange" if atingimento >= 80 else "red")
        
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f"<div class='metric-card'><div class='metric-label'>{label_realizado}</div><div class='metric-value' style='color:#3366cc;'>{int(val_realizado)}</div></div>", unsafe_allow_html=True)
        with c2: st.markdown(f"<div class='metric-card'><div class='metric-label'>{label_meta}</div><div class='metric-value' style='color:#cc0000;'>{int(val_meta)}</div></div>", unsafe_allow_html=True)
        with c3: st.markdown(f"<div class='metric-card'><div class='metric-label'>% Atingimento</div><div class='metric-value' style='color:{cor};'>{atingimento:.2f}%</div></div>", unsafe_allow_html=True)
        st.write("")

    render_kpi("Total Realizado (Equipe Geral)", realizado_geral, "Meta Acumulada (Equipe Geral)", meta_geral)
    render_kpi("Total Realizado (Titulares)", realizado_titulares, "Meta Acumulada (Titulares)", meta_titulares)
    render_kpi("Total Realizado (Apoio)", realizado_apoio, "Meta Acumulada (Apoio)", meta_apoio)

    st.divider()

    # 3. TOP 10 DESTAQUES E BOTTOM 10 ATENÇÃO
    if not df.empty:
        col_rank1, col_rank2 = st.columns(2)
        
        # Agrupa produtividade por pessoa
        df_agrupado = df.groupby('Levantador')['Quantidade Obras'].sum().reset_index()
        df_agrupado['% Meta'] = (df_agrupado['Quantidade Obras'] / meta_acumulada_indiv) * 100
        df_agrupado = df_agrupado.sort_values(by='% Meta', ascending=False)
        
        df_display = df_agrupado.copy()
        df_display['% Meta'] = df_display['% Meta'].map("{:.1f}%".format)
        df_display = df_display.rename(columns={"Levantador": "Colaborador"})
        
        with col_rank1:
            st.markdown("<h4 style='text-align: center; background-color: #66B32E; color: white; padding: 5px;'>TOP 10 - DESTAQUES DA META</h4>", unsafe_allow_html=True)
            st.dataframe(df_display.head(10)[['Colaborador', '% Meta']], use_container_width=True, hide_index=True)
            
        with col_rank2:
            st.markdown("<h4 style='text-align: center; background-color: #D32F2F; color: white; padding: 5px;'>BOTTOM 10 - PONTOS DE ATENÇÃO</h4>", unsafe_allow_html=True)
            df_bottom = df_display.tail(10).sort_values(by='% Meta', ascending=True)
            st.dataframe(df_bottom[['Colaborador', '% Meta']], use_container_width=True, hide_index=True)

        st.divider()

        # 4. CURVA S (PLANEJADO VS REALIZADO SEMANAL)
        st.write("### 📈 Curva S - Meta Planejada vs Execução Real (Semanas)")
        
        df['Semana'] = df['Data'].dt.isocalendar().week
        df_semanal = df.groupby('Semana')['Quantidade Obras'].sum().reset_index()
        
        # Cria a soma acumulada para a Curva S Realizada
        df_semanal['Realizado Acumulado'] = df_semanal['Quantidade Obras'].cumsum()
        
        # Cria a linha de Meta Acumulada por Semana (17.5 obras por pessoa por semana útil)
        meta_semanal_total = 17.5 * len(lista_equipes)
        df_semanal['Meta Acumulada'] = df_semanal.index.map(lambda i: meta_semanal_total * (i + 1))

        # Plotando com Altair (Gráfico de Linhas Duplas)
        base = alt.Chart(df_semanal).encode(x=alt.X('Semana:O', title="Semanas Operacionais"))
        linha_real = base.mark_line(point=True, color='#66B32E', strokeWidth=3).encode(y=alt.Y('Realizado Acumulado:Q', title="Volume de Obras"), tooltip=['Semana', 'Realizado Acumulado'])
        linha_meta = base.mark_line(strokeDash=[5,5], color='#C2C2C2', strokeWidth=3).encode(y='Meta Acumulada:Q', tooltip=['Semana', 'Meta Acumulada'])
        
        st.altair_chart(linha_meta + linha_real, use_container_width=True)

    else:
        st.info("Aguardando lançamentos para gerar Curvas S e Ranks de Produtividade.")
