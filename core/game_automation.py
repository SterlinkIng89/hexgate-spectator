import time
import requests
import logging
import pydirectinput
import threading
import urllib3

# Suprimir advertencias de certificados auto-firmados
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

def wait_for_game_and_setup_camera(delay=3.0):
    """
    Se conecta a la Live Client Data API del juego (puerto 2999).
    Espera a que la partida comience (tiempo > 0) y ejecuta la macro de cámara.
    """
    logger.info("Esperando a que el proceso del juego cargue completamente (Pantalla de carga)...")
    
    url = "https://127.0.0.1:2999/liveclientdata/gamestats"
    game_started = False
    
    # Intentar hasta por 10 minutos (600 iteraciones de 1 segundo)
    for _ in range(600):
        try:
            res = requests.get(url, verify=False, timeout=2)
            if res.status_code == 200:
                data = res.json()
                game_time = data.get("gameTime", 0)
                
                if game_time > 1.0:
                    logger.info(f"Partida iniciada detectada (Tiempo: {game_time}s). Configurando cámara...")
                    game_started = True
                    break
        except requests.exceptions.RequestException:
            # El juego aún no está listo o la pantalla de carga no ha empezado
            pass
            
        time.sleep(1)
        
    if not game_started:
        logger.warning("No se detectó el inicio del juego dentro del tiempo límite.")
        return

    # Esperar el retraso configurado
    logger.info(f"Esperando {delay} segundos (Delay configurado)...")
    time.sleep(delay)
    
    try:
        logger.info("Enviando atajos de teclado (Shift + Z)...")
        # pydirectinput maneja mejor los juegos DirectX
        pydirectinput.keyDown('shift')
        pydirectinput.press('z')
        pydirectinput.keyUp('shift')
        
        time.sleep(0.5)
        
        logger.info("Alejando el zoom (Scroll hacia atrás)...")
        # Scroll hacia atrás 3 veces
        for _ in range(3):
            pydirectinput.scroll(-1000)
            time.sleep(0.2)
            
        logger.info("Configuración de cámara completada.")
    except Exception as e:
        logger.error(f"Error al enviar comandos de teclado: {e}")

def trigger_camera_automation(delay=3.0):
    """
    Lanza el proceso de automatización en un hilo separado para no bloquear el Event Loop asíncrono.
    """
    threading.Thread(target=wait_for_game_and_setup_camera, args=(delay,), daemon=True).start()

if __name__ == "__main__":
    # Prueba manual aislada si se ejecuta directamente
    logging.basicConfig(level=logging.INFO)
    wait_for_game_and_setup_camera()
