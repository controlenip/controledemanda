import customtkinter as ctk
from aba_lancador import AbaLancador
from aba_produtividade import AbaProdutividade
from PIL import Image
import os

# Configurações do App
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Sistema NIP - Grupo Igneo")
        self.geometry("1000x700")

        # Cabeçalho com Logo
        frame_topo = ctk.CTkFrame(self, fg_color="#1C2A59", corner_radius=0, height=80)
        frame_topo.pack(fill="x")
        
        try:
            # Tenta carregar a logo do github/pasta
            img = ctk.CTkImage(light_image=Image.open("LOGO_NIP.png"), size=(120, 60))
            ctk.CTkLabel(frame_topo, image=img, text="").pack(side="left", padx=20, pady=10)
        except Exception:
            ctk.CTkLabel(frame_topo, text="NIP | GRUPO IGNEO", font=("Arial", 20, "bold"), text_color="white").pack(side="left", padx=20, pady=20)

        # Sistema de Abas (Navegação)
        self.tabview = ctk.CTkTabview(self, fg_color="transparent")
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)

        # Criando as abas
        aba1 = self.tabview.add("📝 Lançador Rápido")
        aba2 = self.tabview.add("📊 Produtividade")
        aba3 = self.tabview.add("⚙️ Parâmetros")
        aba4 = self.tabview.add("📈 Dashboard")

        # Instanciando o conteúdo das abas importadas dos outros arquivos
        # Passamos o método carregar_dados da aba de produtividade para o lançador atualizar a tabela ao salvar
        self.view_produtividade = AbaProdutividade(aba2)
        self.view_produtividade.pack(fill="both", expand=True)

        self.view_lancador = AbaLancador(aba1, atualizador_tabela=self.view_produtividade.carregar_dados)
        self.view_lancador.pack(fill="both", expand=True)

        # Placeholders para as próximas abas (Parâmetros e Dashboard)
        ctk.CTkLabel(aba3, text="Configurações e Parâmetros em Desenvolvimento...", font=("Arial", 16)).pack(pady=50)
        ctk.CTkLabel(aba4, text="Gráficos do Dashboard Executivo em Desenvolvimento...", font=("Arial", 16)).pack(pady=50)

if __name__ == "__main__":
    app = App()
    app.mainloop()
