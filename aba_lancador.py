import streamlit as st
import pandas as pd
import os
import io
import datetime
import database

@st.cache_data(ttl=3600)
def carregar_notas_ccs_v2():
    arquivo = "data_2.xlsx" if os.path.exists("data_2.xlsx") else "data.xlsx"
    if os.path.exists(arquivo):
        try:
            df_obras = pd.read_excel(arquivo)
            col_ccs = next((c for c in df_obras.columns if "NOTA CCS" in str(c).upper().replace("_", " ")), None)
            if not col_ccs:
                col_ccs = next((c for c in df_obras.columns if "CCS" in str(c).upper() and "STATUS" not in str(c).upper()), df_obras.columns[1])
                
            valores_ccs = pd.to_numeric(df_obras[col_ccs], errors='coerce').dropna().astype('Int64').astype(str)
            return valores_ccs.unique().tolist()
        except:
            return []
    return []

def gerar_template_lote():
    """Gera um arquivo Excel em branco com as colunas corretas para upload em massa."""
    df_template = pd.DataFrame(columns=[
        "DATA_LEVANTAMENTO (DD/MM/AAAA)", "LEVANTADOR (Ex: EQUIPE 01 - NOME)", 
        "QTD_OBRAS", "NOTAS_CCS (Separadas por virgula)", "PGS", 
        "KM_INICIAL", "KM_FINAL", "STATUS (FINALIZADO ou ANDAMENTO)", 
        "JUSTIFICATIVA", "MOTIVO_OUTROS"
    ])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_template.to_excel(writer, index=False, sheet_name="Lote_Lancamento")
    return output.getvalue()

def render_lancador():
    st.subheader("📝 Módulo de Lançamentos Diários")
    
    if "msg_sucesso" in st.session_state:
        st.success(st.session_state.msg_sucesso)
        del st.session_state.msg_sucesso

    tab1, tab2 = st.tabs(["✍️ Lançamento Individual", "📤 Importação em Massa (Planilha)"])
    
    # ==========================================
    # ABA 1: LANÇAMENTO INDIVIDUAL
    # ==========================================
    with tab1:
        data_lancamento = st.date_input("Data do Levantamento:", format="DD/MM/YYYY")
        lista_equipes = database.get_lista_levantadores()
        
        if not lista_equipes:
            st.error("Nenhuma equipe cadastrada no sistema.")
            return
            
        levantador = st.selectbox("Selecione a Equipe/Levantador:", options=lista_equipes, key="levantador_input")
        st.divider()
        
        qtd_obras = st.number_input("Quantidade de Obras Realizadas no Dia:", min_value=0, step=1, key="qtd_obras_input")
        
        nota_ccs_texto, pgs, km_inicial, km_final, status_lev = "", 0, 0, 0, ""
        notas_ccs_disponiveis = carregar_notas_ccs_v2()
        
        if qtd_obras > 0:
            st.info("💡 Campos adicionais habilitados! Digite os números na caixa abaixo para buscar as obras.")
            if not notas_ccs_disponiveis:
                nota_ccs_texto = st.text_input("NOTA CCS (Digite manualmente):", key="nota_ccs_manual")
            else:
                obras_selecionadas = st.multiselect(
                    "NOTA CCS (Pesquise e Selecione as obras):", 
                    options=notas_ccs_disponiveis,
                    key="nota_ccs_multi"
                )
                nota_ccs_texto = ", ".join(obras_selecionadas)
            
            col1, col2 = st.columns(2)
            with col1: km_inicial = st.number_input("KM INICIAL:", min_value=0, step=1, key="km_ini_input")
            with col2: km_final = st.number_input("KM FINAL:", min_value=0, step=1, key="km_fin_input")
                
            col3, col4 = st.columns(2)
            with col3: status_lev = st.radio("Status do Levantamento:", ["LEVANTAMENTO FINALIZADO", "LEVANTAMENTO EM ANDAMENTO"], key="status_lev_input")
            with col4: pgs = st.number_input("PGS (Postes Levantados):", min_value=0, step=1, key="pgs_input")
                
        st.divider()
        justificativas_lista = ["Nenhuma (Dia Normal)", "Chuva/Clima", "Veículo Quebrado", "Atraso Logístico", "Retrabalho", "Problema Técnico", "Outros"]
        justificativa = st.selectbox("Justificativa Padrão:", options=justificativas_lista, key="just_input")
        
        motivo_outros = ""
        if justificativa == "Outros": motivo_outros = st.text_input("Especifique o motivo detalhadamente:", key="outros_input")
            
        if st.button("💾 SALVAR PRODUÇÃO INDIVIDUAL", type="primary", use_container_width=True):
            if nota_ccs_texto and status_lev == "LEVANTAMENTO FINALIZADO":
                obras_duplicadas = database.verificar_obras_finalizadas(nota_ccs_texto)
                if obras_duplicadas:
                    st.error("🚨 **ALERTA DE RETRABALHO BLOQUEADO!** Obras já finalizadas no histórico.")
                    return 
            
            if km_final > 0 and km_inicial > 0 and km_final < km_inicial:
                st.error("⚠️ O KM Final não pode ser menor que o KM Inicial!")
                return
                
            novo_dado = {
                "DATA_LEVANTAMENTO": data_lancamento.strftime("%d/%m/%Y"),
                "Levantador": levantador, "Quantidade Obras": qtd_obras, "Nota CCS": nota_ccs_texto,
                "PGS": pgs, "KM Inicial": km_inicial, "KM Final": km_final,
                "Status Levantamento": status_lev, "Justificativa": justificativa, "Motivo Outros": motivo_outros
            }
            database.salvar_registro(novo_dado)
            
            if nota_ccs_texto:
                database.atualizar_obra_na_base(nota_ccs_texto, levantador, data_lancamento.strftime("%d/%m/%Y"), pgs, status_lev)
            
            st.session_state.msg_sucesso = f"✅ Produção individual salva para {levantador}!"
            st.session_state.qtd_obras_input = 0
            if hasattr(st, "rerun"): st.rerun()
            else: st.experimental_rerun()

    # ==========================================
    # ABA 2: IMPORTAÇÃO EM MASSA (LOTE)
    # ==========================================
    with tab2:
        st.write("### 📤 Importação em Lote via Planilha")
        st.write("Se a internet caiu no campo ou você recebeu dezenas de fichas de papel, preencha tudo no Excel e suba de uma vez aqui.")
        
        st.download_button(
            label="⬇️ 1. Baixar Planilha Modelo (Template)",
            data=gerar_template_lote(),
            file_name="Template_Lancamento_Lote_NIP.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.write("---")
        arquivo_lote = st.file_uploader("📂 2. Suba a planilha preenchida aqui (.xlsx)", type=["xlsx"])
        
        if arquivo_lote and st.button("🚀 PROCESSAR E SALVAR LOTE", type="primary"):
            with st.spinner("Processando registros e atualizando as bases... Isso pode levar alguns segundos."):
                try:
                    df_lote = pd.read_excel(arquivo_lote)
                    registros_salvos = 0
                    
                    for idx, row in df_lote.iterrows():
                        if pd.isna(row.get("DATA_LEVANTAMENTO (DD/MM/AAAA)")) or pd.isna(row.get("LEVANTADOR (Ex: EQUIPE 01 - NOME)")):
                            continue # Pula linhas vazias
                            
                        dt_bruta = row["DATA_LEVANTAMENTO (DD/MM/AAAA)"]
                        if isinstance(dt_bruta, datetime.datetime): dt_str = dt_bruta.strftime("%d/%m/%Y")
                        else: dt_str = str(dt_bruta).strip()
                            
                        equipe_nome = str(row["LEVANTADOR (Ex: EQUIPE 01 - NOME)"]).strip()
                        qtd = int(row.get("QTD_OBRAS", 0)) if not pd.isna(row.get("QTD_OBRAS")) else 0
                        notas = str(row.get("NOTAS_CCS (Separadas por virgula)", "")).strip() if not pd.isna(row.get("NOTAS_CCS (Separadas por virgula)")) else ""
                        pgs_val = int(row.get("PGS", 0)) if not pd.isna(row.get("PGS")) else 0
                        km_i = float(row.get("KM_INICIAL", 0)) if not pd.isna(row.get("KM_INICIAL")) else 0
                        km_f = float(row.get("KM_FINAL", 0)) if not pd.isna(row.get("KM_FINAL")) else 0
                        
                        status = str(row.get("STATUS (FINALIZADO ou ANDAMENTO)", "LEVANTAMENTO FINALIZADO")).strip()
                        if "ANDAMENTO" in status.upper(): status = "LEVANTAMENTO EM ANDAMENTO"
                        else: status = "LEVANTAMENTO FINALIZADO"
                            
                        just = str(row.get("JUSTIFICATIVA", "Nenhuma (Dia Normal)")).strip()
                        outros = str(row.get("MOTIVO_OUTROS", "")).strip()
                        if pd.isna(just) or just == "": just = "Nenhuma (Dia Normal)"
                        if pd.isna(outros): outros = ""

                        novo_dado_lote = {
                            "DATA_LEVANTAMENTO": dt_str, "Levantador": equipe_nome,
                            "Quantidade Obras": qtd, "Nota CCS": notas, "PGS": pgs_val,
                            "KM Inicial": km_i, "KM Final": km_f, "Status Levantamento": status,
                            "Justificativa": just, "Motivo Outros": outros
                        }
                        
                        database.salvar_registro(novo_dado_lote)
                        if notas:
                            database.atualizar_obra_na_base(notas, equipe_nome, dt_str, pgs_val, status)
                        registros_salvos += 1
                        
                    st.session_state.msg_sucesso = f"🎉 Sucesso! {registros_salvos} lançamentos foram salvos em lote e as obras foram atualizadas."
                    if hasattr(st, "rerun"): st.rerun()
                    else: st.experimental_rerun()
                    
                except Exception as e:
                    st.error(f"Erro ao ler o arquivo Excel: {e}")
