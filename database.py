import pandas as pd
import os

ARQUIVO_DADOS = "Controle_Produtividade_NIP.xlsx"

def iniciar_banco():
    """Cria a planilha se ela não existir com as colunas base."""
    if not os.path.exists(ARQUIVO_DADOS):
        df = pd.DataFrame(columns=[
            "Data", "Colaborador", "Nota CCS", "Qtd Postes", 
            "KM Inicial", "KM Final", "Justificativa", "Dias Trabalhados"
        ])
        df.to_excel(ARQUIVO_DADOS, index=False)

def salvar_registro(novo_dado):
    """Salva um novo dicionário de dados como uma nova linha no Excel."""
    iniciar_banco()
    df = pd.read_excel(ARQUIVO_DADOS)
    df = pd.concat([df, pd.DataFrame([novo_dado])], ignore_index=True)
    df.to_excel(ARQUIVO_DADOS, index=False)

def ler_registros():
    """Retorna os dados do Excel como um DataFrame do Pandas."""
    iniciar_banco()
    return pd.read_excel(ARQUIVO_DADOS)
