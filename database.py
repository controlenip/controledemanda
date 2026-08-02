import pandas as pd
import os

ARQUIVO_DADOS = "Produtividade_Levantadores_NIP.xlsx"

# Lista Base de Colaboradores (Você pode alterar os nomes depois)
LEVANTADORES_BASE = ["Levantador 01", "Levantador 02", "Levantador 03", "Levantador 04", "Levantador 05"]

# Gerando automaticamente 10 espaços para Apoio
LEVANTADORES_APOIO = [f"Apoio {i:02d}" for i in range(1, 11)]
TODOS_LEVANTADORES = LEVANTADORES_BASE + LEVANTADORES_APOIO

def iniciar_banco():
    if not os.path.exists(ARQUIVO_DADOS):
        df = pd.DataFrame(columns=["Data", "Levantador", "Quantidade Obras", "Justificativa"])
        df.to_excel(ARQUIVO_DADOS, index=False)

def salvar_registro(novo_dado):
    iniciar_banco()
    df = pd.read_excel(ARQUIVO_DADOS)
    df = pd.concat([df, pd.DataFrame([novo_dado])], ignore_index=True)
    df.to_excel(ARQUIVO_DADOS, index=False)

def ler_registros():
    iniciar_banco()
    df = pd.read_excel(ARQUIVO_DADOS)
    # Garante que a coluna de data seja lida como data pelo sistema
    df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
    return df
