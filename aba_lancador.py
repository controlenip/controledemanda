import streamlit as st
import pandas as pd
import os
import database

@st.cache_data
def carregar_notas_ccs():
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

def render_lancador():
    st.subheader("📝 Lançamento Manual Inteligente (Com Auditoria)")
    
    if "msg_sucesso" in st.session_state:
        st.success(st.session_state.msg_sucesso)
        del st.session_state.msg_sucesso

    data_lancamento = st.date_input("Data do Levantamento:", format="DD/MM/YYYY")
    lista_equipes = database.get_lista_levantadores()
    
    if not lista_equipes:
        st.error("Nenhuma equipe cadastrada no sistema.")
        return
        
    levantador = st.selectbox("Selecione a Equipe/Levantador:", options=lista_equipes, key="levantador_input")
    st.divider()
    
    qtd_obras = st.number_input("Quantidade de Obras Realizadas no Dia:", min_value=0, step=1, key="qtd_obras_input")
    
    nota_ccs_texto, pgs, km_inicial, km_final, status_lev = "", 0, 0, 0, ""
    notas_ccs_disponiveis = carregar_notas_ccs()
    
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
    
    justificativas_lista = [
        "Nenhuma (Dia Normal)", "Chuva/Clima", "Veículo Quebrado", 
        "Atraso Logístico (Combustível, OnFly)", "Retrabalho", 
        "Problema Técnico", "Outros"
    ]
    justificativa = st.selectbox("Justificativa Padrão:", options=justificativas_lista, key="just_input")
    
    motivo_outros = ""
    if justificativa == "Outros": motivo_outros = st.text_input("Especifique o motivo detalhadamente:", key="outros_input")
        
    if st.button("💾 SALVAR PRODUÇÃO DIÁRIA", type="primary", use_container_width=True):
        
        # 🛡️ TRAVA ANTI-RETRABALHO (Evita Lançar Duplicidade)
        if nota_ccs_texto and status_lev == "LEVANTAMENTO FINALIZADO":
            obras_duplicadas = database.verificar_obras_finalizadas(nota_ccs_texto)
            if obras_duplicadas:
                st.error("🚨 **ALERTA DE RETRABALHO BLOQUEADO!** As seguintes obras já constam como FINALIZADAS no sistema:")
                for dup in obras_duplicadas:
                    st.warning(f"**Nota CCS:** {dup['nota']} | **Finalizada por:** {dup['levantador']} | **Data:** {dup['data'][:10]}")
                st.error("Verifique a seleção de obras. Não é possível salvar registros duplicados.")
                return # Bloqueia o processo de salvar
        
        # Validação Anti-Erros de KM
        if km_final > 0 and km_inicial > 0 and km_final < km_inicial:
            st.error("⚠️ Validação Anti-Erros: O KM Final não pode ser menor que o KM Inicial!")
            return
            
        if qtd_obras > 0 and not nota_ccs_texto:
            st.error("⚠️ Selecione pelo menos uma Nota CCS.")
            return
            
        km_rodado = km_final - km_inicial
        if km_rodado > 400 and qtd_obras == 0:
            st.warning("⚠️ Atenção: Quilometragem informada muito alta sem obras associadas. Verifique os valores.")
            
        novo_dado = {
            "DATA_LEVANTAMENTO": data_lancamento.strftime("%d/%m/%Y"),
            "Levantador": levantador,
            "Quantidade Obras": qtd_obras,
            "Nota CCS": nota_ccs_texto,
            "PGS": pgs, "KM Inicial": km_inicial, "KM Final": km_final,
            "Status Levantamento": status_lev, "Justificativa": justificativa, "Motivo Outros": motivo_outros
        }
        database.salvar_registro(novo_dado)
        
        if nota_ccs_texto:
            database.atualizar_obra_na_base(
                nota_ccs_texto, levantador, data_lancamento.strftime("%d/%m/%Y"), pgs, status_lev
            )
        
        st.session_state.msg_sucesso = f"✅ Produção salva e 'Status das Obras' atualizado para {levantador}!"
        
        st.session_state.qtd_obras_input = 0
        if "nota_ccs_multi" in st.session_state: st.session_state.nota_ccs_multi = []
        if "km_ini_input" in st.session_state: st.session_state.km_ini_input = 0
        if "km_fin_input" in st.session_state: st.session_state.km_fin_input = 0
        if "pgs_input" in st.session_state: st.session_state.pgs_input = 0
        
        if hasattr(st, "rerun"): st.rerun()
        else: st.experimental_rerun()
