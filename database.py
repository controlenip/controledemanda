import pandas as pd
import os

ARQUIVO_DADOS = "Produtividade_Levantadores_NIP.xlsx"
ARQUIVO_EQUIPES = "Equipes_Gerenciadas.xlsx"

def iniciar_bancos():
    # 1. Inicia Banco de Produtividade com as novas colunas
    if not os.path.exists(ARQUIVO_DADOS):
        df = pd.DataFrame(columns=[
            "Data", "Levantador", "Quantidade Obras", 
            "Nota CCS", "PGS", "KM Inicial", "KM Final", 
            "Status Levantamento", "Justificativa", "Motivo Outros"
        ])
        df.to_excel(ARQUIVO_DADOS, index=False)
        
    # 2. Inicia Banco de Equipes
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
    df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
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
