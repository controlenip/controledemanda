import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
import database

class AbaLancador(ctk.CTkFrame):
    def __init__(self, master, atualizador_tabela=None):
        super().__init__(master, fg_color="transparent")
        self.atualizador_tabela = atualizador_tabela

        titulo = ctk.CTkLabel(self, text="FORMULÁRIO DE LANÇAMENTO DIÁRIO", font=("Arial", 18, "bold"), text_color="#1C2A59")
        titulo.pack(pady=20)

        # Container para os campos ficarem centralizados
        frame_form = ctk.CTkFrame(self)
        frame_form.pack(pady=10, padx=20, fill="both", expand=True)

        self.entradas = {}
        campos = ["Colaborador", "Nota CCS", "Qtd Postes (PGS)", "KM Inicial", "KM Final", "Dias Trabalhados"]
        
        for campo in campos:
            ctk.CTkLabel(frame_form, text=campo + ":", font=("Arial", 12, "bold")).pack(anchor="w", padx=20, pady=(10, 0))
            ent = ctk.CTkEntry(frame_form, width=400)
            ent.pack(padx=20, pady=5)
            self.entradas[campo] = ent

        self.entradas["Dias Trabalhados"].insert(0, "1")

        # Justificativa
        ctk.CTkLabel(frame_form, text="Justificativa (Opcional):", font=("Arial", 12, "bold")).pack(anchor="w", padx=20, pady=(10, 0))
        self.cb_just = ctk.CTkComboBox(frame_form, values=["", "Chuva/Clima", "Veículo Quebrado", "Atraso Logístico"], width=400)
        self.cb_just.pack(padx=20, pady=5)

        # Botões
        btn_salvar = ctk.CTkButton(self, text="SALVAR DADOS", fg_color="#66B32E", font=("Arial", 14, "bold"), command=self.salvar)
        btn_salvar.pack(pady=10)

    def salvar(self):
        colab = self.entradas["Colaborador"].get()
        postes = self.entradas["Qtd Postes (PGS)"].get()

        if not colab or not postes:
            messagebox.showwarning("Aviso", "Preencha Colaborador e Postes!")
            return

        novo_dado = {
            "Data": datetime.now().strftime("%d/%m/%Y"),
            "Colaborador": colab,
            "Nota CCS": self.entradas["Nota CCS"].get(),
            "Qtd Postes": postes,
            "KM Inicial": self.entradas["KM Inicial"].get(),
            "KM Final": self.entradas["KM Final"].get(),
            "Justificativa": self.cb_just.get(),
            "Dias Trabalhados": self.entradas["Dias Trabalhados"].get()
        }

        try:
            database.salvar_registro(novo_dado)
            messagebox.showinfo("Sucesso", "Registrado com sucesso!")
            
            # Limpa apenas os dados rotativos
            self.entradas["Nota CCS"].delete(0, 'end')
            self.entradas["Qtd Postes (PGS)"].delete(0, 'end')
            
            # Atualiza a tabela na outra aba, se ela existir
            if self.atualizador_tabela:
                self.atualizador_tabela()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar: {e}")
