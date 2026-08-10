import customtkinter as ctk
import logging
import queue
from core.hexgate import start_bot, stop_bot

class TextboxHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configuración de Ventana
        self.title("Hexgate - Scrim Auto Spectator")
        self.geometry("650x700")
        self.resizable(False, False)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.is_running = False
        self.log_queue = queue.Queue()
        self.setup_logging()

        # --- UI Layout ---
        
        # Frame Superior (Título y Estado)
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.pack(pady=(20, 10), padx=20, fill="x")
        
        self.title_label = ctk.CTkLabel(self.top_frame, text="Hexgate Spectator", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.pack(pady=(10, 5))
        
        self.status_label = ctk.CTkLabel(self.top_frame, text="ESTADO: Detenido", font=ctk.CTkFont(size=14), text_color="gray")
        self.status_label.pack(pady=(0, 10))
        
        # Frame de Configuración
        self.config_frame = ctk.CTkFrame(self)
        self.config_frame.pack(pady=10, padx=20, fill="x")
        
        # Grid para alinear inputs
        self.config_frame.columnconfigure(0, weight=1)
        self.config_frame.columnconfigure(1, weight=2)
        
        # Lobby Name
        ctk.CTkLabel(self.config_frame, text="Nombre de la sala:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.entry_lobby = ctk.CTkEntry(self.config_frame, placeholder_text="Ej: SCRIM_TEST")
        self.entry_lobby.insert(0, "SCRIM_TEST")
        self.entry_lobby.grid(row=0, column=1, padx=10, pady=10, sticky="we")
        
        # Passwords
        ctk.CTkLabel(self.config_frame, text="Contraseñas (separadas por coma):").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.entry_passwords = ctk.CTkEntry(self.config_frame, placeholder_text="123, test, scrim")
        self.entry_passwords.grid(row=1, column=1, padx=10, pady=10, sticky="we")
        
        # Camera Delay
        ctk.CTkLabel(self.config_frame, text="Retraso de Cámara (segundos):").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.entry_delay = ctk.CTkEntry(self.config_frame)
        self.entry_delay.insert(0, "3")
        self.entry_delay.grid(row=2, column=1, padx=10, pady=10, sticky="we")
        
        # Invite Only Mode
        self.check_invite_only = ctk.CTkCheckBox(self.config_frame, text="Modo 'Solo esperar invitación' (No buscar sala)")
        self.check_invite_only.grid(row=3, column=0, columnspan=2, padx=10, pady=15)
        
        # Botón Start/Stop
        self.btn_toggle = ctk.CTkButton(self, text="INICIAR BOT", command=self.toggle_bot, fg_color="green", hover_color="darkgreen", height=40)
        self.btn_toggle.pack(pady=10, padx=20, fill="x")
        
        # Frame Inferior (Logs)
        self.log_box = ctk.CTkTextbox(self, state="disabled", fg_color="black", text_color="#00FF00", font=("Consolas", 12))
        self.log_box.pack(pady=(10, 20), padx=20, fill="both", expand=True)
        
        self.after(100, self.process_log_queue)

    def setup_logging(self):
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
        gui_handler = TextboxHandler(self.log_queue)
        gui_handler.setFormatter(formatter)
        logger.addHandler(gui_handler)

    def process_log_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(100, self.process_log_queue)

    def update_status(self, text):
        self.after(0, lambda: self.status_label.configure(text=f"ESTADO: {text}", text_color="white"))

    def toggle_bot(self):
        if not self.is_running:
            # Recopilar configuración
            passwords_raw = self.entry_passwords.get()
            passwords = [p.strip() for p in passwords_raw.split(",")] if passwords_raw else []
            
            try:
                cam_delay = float(self.entry_delay.get())
            except ValueError:
                cam_delay = 3.0
            
            config_data = {
                "lobby_name": self.entry_lobby.get().strip(),
                "passwords": passwords,
                "camera_delay": cam_delay,
                "invite_only": self.check_invite_only.get() == 1
            }
            
            # Bloquear inputs
            self.entry_lobby.configure(state="disabled")
            self.entry_passwords.configure(state="disabled")
            self.entry_delay.configure(state="disabled")
            self.check_invite_only.configure(state="disabled")
            
            self.is_running = True
            self.btn_toggle.configure(text="DETENER BOT", fg_color="red", hover_color="darkred")
            self.status_label.configure(text_color="white")
            start_bot(self.update_status, config_data)
        else:
            self.is_running = False
            self.btn_toggle.configure(text="INICIAR BOT", fg_color="green", hover_color="darkgreen")
            self.status_label.configure(text="ESTADO: Detenido", text_color="gray")
            
            # Desbloquear inputs
            self.entry_lobby.configure(state="normal")
            self.entry_passwords.configure(state="normal")
            self.entry_delay.configure(state="normal")
            self.check_invite_only.configure(state="normal")
            
            stop_bot()

def run_app():
    app = App()
    app.mainloop()
