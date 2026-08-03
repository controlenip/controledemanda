import pandas as pd
import os

ARQUIVO_DADOS = "Produtividade_Levantadores_NIP.xlsx"
ARQUIVO_EQUIPES = "Equipes_Gerenciadas.xlsx"

def iniciar_bancos():
    if not os.path.exists(ARQUIVO_DADOS):
        df = pd.DataFrame(columns=[
            "DATA_LEVANTAMENTO", "Levantador", "Quantidade Obras", 
            "Nota CCS", "PGS", "KM Inicial", "KM Final", 
            "Status Levantamento", "Justificativa", "Motivo Outros"
        ])
        df.to_excel(ARQUIVO_DADOS, index=False)
        
    if not os.path.exists(ARQUIVO_EQUIPES):
        if os.path.exists("equipes de campo.xlsx"):
            df_eq = pd.read_excel("equipes de campo.xlsx", sheet_name="Planilha1")
            df_eq = df_eq[['EQUIPE', 'COLABORADOR']].dropna()
        else:
            df_eq = pd.DataFrame(columns=["EQUIPE", "COLABORADOR"])
        df_eq.to_excel(ARQUIVO_EQUIPES, index=False)

def salvar_registro(novo_dado):
    iniciar_bancos()
    df = pd.read_excel(ARQUIVO_DADOS)
    df = pd.concat([df, pd.DataFrame([novo_dado])], ignore_index=True)
    df.to_excel(ARQUIVO_DADOS, index=False)

def ler_registros():
    iniciar_bancos()
    df = pd.read_excel(ARQUIVO_DADOS)
    df['DATA_LEVANTAMENTO'] = pd.to_datetime(df['DATA_LEVANTAMENTO'], format='%d/%m/%Y', errors='coerce')
    df['Data'] = df['DATA_LEVANTAMENTO'] 
    return df

def ler_equipes_df():
    iniciar_bancos()
    return pd.read_excel(ARQUIVO_EQUIPES)

def salvar_equipes_df(df):
    df.to_excel(ARQUIVO_EQUIPES, index=False)

def get_lista_levantadores():
    df = ler_equipes_df()
    lista = []
    for _, row in df.iterrows():
        lista.append(f"{row['EQUIPE']} - {row['COLABORADOR']}")
    return lista

def atualizar_obra_na_base(notas_ccs_str, levantador, data_levantamento, pgs, status_lev):
    arquivo_base = "data_2.xlsx" if os.path.exists("data_2.xlsx") else "data.xlsx"
    
    if os.path.exists(arquivo_base):
        try:
            df_obras = pd.read_excel(arquivo_base)
            col_ccs = "Nota CCS" if "Nota CCS" in df_obras.columns else df_obras.columns[0]
            col_lev = next((c for c in df_obras.columns if "LEVANTADOR" in str(c).upper()), "LEVANTADOR")
            col_data = next((c for c in df_obras.columns if "DATA_LEVANTAMENTO" in str(c).upper()), "DATA_LEVANTAMENTO")
            col_pgs = next((c for c in df_obras.columns if "PGS" in str(c).upper()), "PGS")
            col_status = next((c for c in df_obras.columns if "STATUS ATUAL" in str(c).upper()), "Status Atual(Levantamento)")
            
            notas_lista = [n.strip() for n in notas_ccs_str.split(",") if n.strip()]
            df_ccs_str = pd.to_numeric(df_obras[col_ccs], errors='coerce').fillna(0).astype('Int64').astype(str)
            
            mask = df_ccs_str.isin(notas_lista)
            
            if mask.any():
                for col in [col_lev, col_data, col_pgs, col_status]:
                    if col not in df_obras.columns: df_obras[col] = None
                        
                df_obras.loc[mask, col_lev] = levantador
                df_obras.loc[mask, col_data] = data_levantamento
                df_obras.loc[mask, col_pgs] = pgs
                df_obras.loc[mask, col_status] = status_lev
                
                df_obras.to_excel(arquivo_base, index=False)
        except Exception as e:
            print(f"Erro ao atualizar base de obras: {e}")
