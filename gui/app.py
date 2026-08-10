import customtkinter as ctk
import logging
import queue
import json
import os
from core.hexgate import start_bot, stop_bot

# Configuración de usuario guardada en AppData
APPDATA = os.getenv('APPDATA', os.path.expanduser('~'))
CONFIG_DIR = os.path.join(APPDATA, 'HexgateSpectator')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

# Crear carpeta si no existe
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

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
        
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.pack(pady=(20, 10), padx=20, fill="x")
        
        self.title_label = ctk.CTkLabel(self.top_frame, text="Hexgate Spectator", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.pack(pady=(10, 5))
        
        self.status_label = ctk.CTkLabel(self.top_frame, text="ESTADO: Detenido", font=ctk.CTkFont(size=14), text_color="gray")
        self.status_label.pack(pady=(0, 10))
        
        self.config_frame = ctk.CTkFrame(self)
        self.config_frame.pack(pady=10, padx=20, fill="x")
        
        self.config_frame.columnconfigure(0, weight=1)
        self.config_frame.columnconfigure(1, weight=2)
        
        ctk.CTkLabel(self.config_frame, text="Nombre de la sala:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.entry_lobby = ctk.CTkEntry(self.config_frame, placeholder_text="Ej: SCRIM_TEST")
        self.entry_lobby.grid(row=0, column=1, padx=10, pady=10, sticky="we")
        
        ctk.CTkLabel(self.config_frame, text="Contraseñas (separadas por coma):").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.entry_passwords = ctk.CTkEntry(self.config_frame, placeholder_text="123, test, scrim")
        self.entry_passwords.grid(row=1, column=1, padx=10, pady=10, sticky="we")
        
        ctk.CTkLabel(self.config_frame, text="Retraso de Cámara (segundos):").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.entry_delay = ctk.CTkEntry(self.config_frame)
        self.entry_delay.grid(row=2, column=1, padx=10, pady=10, sticky="we")
        
        self.check_invite_only = ctk.CTkCheckBox(self.config_frame, text="Modo 'Solo esperar invitación' (No buscar sala)")
        self.check_invite_only.grid(row=3, column=0, columnspan=2, padx=10, pady=15)
        
        self.btn_toggle = ctk.CTkButton(self, text="INICIAR BOT", command=self.toggle_bot, fg_color="green", hover_color="darkgreen", height=40)
        self.btn_toggle.pack(pady=10, padx=20, fill="x")
        
        self.log_box = ctk.CTkTextbox(self, state="disabled", fg_color="black", text_color="#00FF00", font=("Consolas", 12))
        self.log_box.pack(pady=(10, 20), padx=20, fill="both", expand=True)
        
        self.after(100, self.process_log_queue)
        
        # Cargar configuración guardada (si existe)
        self.load_config()

    def load_config(self):
        """Carga la configuración desde config.json e inicializa los campos."""
        default_config = {
            "lobby_name": "SCRIM_TEST",
            "passwords": "123",
            "camera_delay": "3",
            "invite_only": 0
        }
        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    saved_config = json.load(f)
                    default_config.update(saved_config)
            except Exception as e:
                logging.error(f"Error al cargar configuración: {e}")
        
        self.entry_lobby.insert(0, default_config.get("lobby_name", ""))
        self.entry_passwords.insert(0, default_config.get("passwords", ""))
        self.entry_delay.insert(0, str(default_config.get("camera_delay", "3")))
        
        if default_config.get("invite_only", 0):
            self.check_invite_only.select()
        else:
            self.check_invite_only.deselect()

    def save_config(self):
        """Guarda la configuración actual en config.json."""
        config_data = {
            "lobby_name": self.entry_lobby.get().strip(),
            "passwords": self.entry_passwords.get().strip(),
            "camera_delay": self.entry_delay.get().strip(),
            "invite_only": self.check_invite_only.get()
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config_data, f, indent=4)
        except Exception as e:
            logging.error(f"Error al guardar configuración: {e}")

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
            # Guardar preferencias al iniciar
            self.save_config()
            
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
            
            self.entry_lobby.configure(state="normal")
            self.entry_passwords.configure(state="normal")
            self.entry_delay.configure(state="normal")
            self.check_invite_only.configure(state="normal")
            
            stop_bot()

def run_app():
    app = App()
    app.mainloop()
