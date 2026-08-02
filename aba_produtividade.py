import customtkinter as ctk
from tkinter import ttk
import database

class AbaProdutividade(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        titulo = ctk.CTkLabel(self, text="DADOS DA EQUIPE (BANCO DE DADOS)", font=("Arial", 18, "bold"), text_color="#1C2A59")
        titulo.pack(pady=20)

        # Configuração da Tabela
        colunas = ("Data", "Colaborador", "CCS", "Postes", "KM Ini", "KM Fin", "Justificativa")
        self.tree = ttk.Treeview(self, columns=colunas, show="headings", height=20)
        
        larguras = [80, 150, 100, 60, 60, 60, 150]
        for col, larg in zip(colunas, larguras):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=larg, anchor="center")

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(fill="both", expand=True, padx=20, pady=10)
        scrollbar.place(relx=0.98, rely=0.15, relheight=0.8)

        self.carregar_dados()

    def carregar_dados(self):
        """Limpa a tabela atual e puxa os dados novos do Excel"""
        for row in self.tree.get_children():
            self.tree.delete(row)
            
        df = database.ler_registros()
        df_recentes = df.tail(100).iloc[::-1] # Mostra os últimos 100 registros
        
        for index, row in df_recentes.iterrows():
            self.tree.insert("", "end", values=(
                row["Data"], row["Colaborador"], row["Nota CCS"], 
                row["Qtd Postes"], row["KM Inicial"], row["KM Final"], row["Justificativa"]
            ))
