import importlib.util
import os
import sys
import tkinter as tk
from tkinter import messagebox

from extrator_porto_seguro import App as ExtratorApp


def _candidate_base_dirs():
    dirs = []
    if getattr(sys, "frozen", False):
        dirs.append(os.path.dirname(sys.executable))
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            dirs.append(meipass)
    dirs.append(os.path.dirname(os.path.abspath(__file__)))

    unique_dirs = []
    for path in dirs:
        if path and path not in unique_dirs:
            unique_dirs.append(path)
    return unique_dirs


def _find_file(*names):
    for base_dir in _candidate_base_dirs():
        for name in names:
            candidate = os.path.join(base_dir, name)
            if os.path.exists(candidate):
                return candidate
    raise FileNotFoundError(f"Arquivo nao encontrado. Procurado em: {', '.join(names)}")


BASE_DIR = _candidate_base_dirs()[0]
DASHBOARD_PATH = None


def carregar_dashboard_class():
    dashboard_path = _find_file("dashboardtela.py", "dashboardtela (4).py")
    spec = importlib.util.spec_from_file_location("dashboard_master_prime", dashboard_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Nao foi possivel carregar o dashboard em: {dashboard_path}")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.DashboardTV

try:
    from dashboardtela import DashboardTV
except Exception:
    DashboardTV = carregar_dashboard_class()


class CentralIntegrada(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Central Integrada - Extrator e Dashboard")
        self.geometry("520x360+80+80")
        self.minsize(480, 320)
        self.configure(bg="#0F172A")

        self.extrator_window = None
        self.dashboard_window = None

        self._build_ui()

    def _build_ui(self):
        wrapper = tk.Frame(self, bg="#0F172A", padx=28, pady=24)
        wrapper.pack(fill="both", expand=True)

        tk.Label(
            wrapper,
            text="Central Integrada",
            font=("Segoe UI", 20, "bold"),
            bg="#0F172A",
            fg="#F8FAFC",
        ).pack(anchor="w")

        tk.Label(
            wrapper,
            text="Abra o extrator, o dashboard, ou os dois juntos sem que uma ferramenta force o foco da outra.",
            font=("Segoe UI", 10),
            bg="#0F172A",
            fg="#CBD5E1",
            justify="left",
            wraplength=430,
        ).pack(anchor="w", pady=(8, 20))

        card = tk.Frame(
            wrapper,
            bg="#111827",
            highlightbackground="#334155",
            highlightthickness=1,
            padx=18,
            pady=18,
        )
        card.pack(fill="both", expand=True)

        self.var_headless = tk.BooleanVar(value=True)

        tk.Checkbutton(
            card,
            text="Ao abrir o extrator pela central, esconder o navegador durante a extracao",
            variable=self.var_headless,
            font=("Segoe UI", 10),
            bg="#111827",
            fg="#E2E8F0",
            activebackground="#111827",
            activeforeground="#E2E8F0",
            selectcolor="#1E293B",
            wraplength=400,
            justify="left",
        ).pack(anchor="w", pady=(0, 16))

        botoes = [
            ("Abrir extrator", "#2563EB", self.abrir_extrator),
            ("Abrir dashboard", "#0F766E", self.abrir_dashboard),
            ("Abrir os dois", "#EA580C", self.abrir_ambos),
            ("Fechar janelas abertas", "#475569", self.fechar_janelas),
        ]

        for texto, cor, comando in botoes:
            tk.Button(
                card,
                text=texto,
                font=("Segoe UI", 11, "bold"),
                bg=cor,
                fg="white",
                activebackground=cor,
                activeforeground="white",
                relief="flat",
                cursor="hand2",
                pady=10,
                command=comando,
            ).pack(fill="x", pady=5)

        tk.Label(
            card,
            text="Os scripts originais continuam funcionando individualmente. Esta central so organiza a abertura conjunta.",
            font=("Segoe UI", 9),
            bg="#111827",
            fg="#94A3B8",
            justify="left",
            wraplength=400,
        ).pack(anchor="w", pady=(16, 0))

        self.protocol("WM_DELETE_WINDOW", self._encerrar_central)

    def abrir_extrator(self):
        if self.extrator_window and self.extrator_window.winfo_exists():
            self.extrator_window.deiconify()
            self.extrator_window.lift()
            return

        self.extrator_window = tk.Toplevel(self)
        self.extrator_window.transient(self)
        self.extrator_window.protocol("WM_DELETE_WINDOW", self._fechar_extrator)

        mostrar_navegador = not self.var_headless.get()
        ExtratorApp(self.extrator_window, mostrar_navegador_inicial=mostrar_navegador)

    def abrir_dashboard(self):
        if self.dashboard_window and self.dashboard_window.winfo_exists():
            self.dashboard_window.deiconify()
            self.dashboard_window.lift()
            return

        self.withdraw()
        self.dashboard_window = DashboardTV(
            master=self,
            keep_on_top=True,
            exit_on_close=False,
        )
        self.dashboard_window.protocol("WM_DELETE_WINDOW", self._fechar_dashboard)

    def abrir_ambos(self):
        self.abrir_dashboard()
        self.abrir_extrator()

    def _fechar_extrator(self):
        if self.extrator_window and self.extrator_window.winfo_exists():
            self.extrator_window.destroy()
        self.extrator_window = None

    def _fechar_dashboard(self):
        if self.dashboard_window and self.dashboard_window.winfo_exists():
            self.dashboard_window._sair()
        self.dashboard_window = None
        self.deiconify()

    def fechar_janelas(self):
        self._fechar_extrator()
        self._fechar_dashboard()

    def _encerrar_central(self):
        if messagebox.askyesno("Fechar central", "Deseja encerrar a central e todas as janelas abertas?"):
            self.fechar_janelas()
            self.destroy()


if __name__ == "__main__":
    app = CentralIntegrada()
    app.mainloop()
