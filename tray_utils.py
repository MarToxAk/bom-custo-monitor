import threading
import os
import sys
from PIL import Image
import pystray

icone_bandeja = None

def criar_icone_bandeja():
    # Usa o ícone status.ico se existir, senão gera um círculo azul
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)
    ico_path = os.path.join(base_path, 'status.ico')
    if os.path.exists(ico_path):
        try:
            return Image.open(ico_path)
        except Exception:
            pass  # Se falhar, cai para o ícone padrão
    if Image is None:
        return None
    img = Image.new('RGBA', (32, 32), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 28, 28), fill=(0, 128, 255, 255))
    return img

def restaurar_janela(window):
    def _restore():
        window.deiconify()
        window.lift()
        window.focus_force()
    window.after(0, _restore)
    global icone_bandeja
    if icone_bandeja:
        icone_bandeja.stop()
        icone_bandeja = None

def minimizar_para_bandeja(window, messagebox, on_close_callback=None):
    global icone_bandeja
    if pystray is None:
        messagebox.showinfo("Bandeja", "Para usar este recurso, instale as dependências: pystray, pillow\nUse: pip install pystray pillow")
        return
    window.withdraw()
    # Notificação ao minimizar
    try:
        from winotify import Notification
        toast = Notification(
            app_id="Bom Custo",
            title="Bom Custo minimizado",
            msg="O sistema continua rodando em segundo plano na bandeja."
        )
        toast.show()
    except Exception:
        pass  # winotify não instalado ou erro, ignora
    if icone_bandeja is not None:
        return  # Já está na bandeja
    # Caminho absoluto para o status.ico
    icon_path = os.path.join(os.path.dirname(__file__), 'status.ico')
    image = Image.open(icon_path)
    from functools import partial
    def sair_da_bandeja(icon, item):
        # Corrigido: nunca fecha o app automaticamente ao sair da bandeja
        window.after(0, window.deiconify)  # Apenas restaura a janela
    menu = pystray.Menu(
        pystray.MenuItem('Restaurar', lambda icon, item: restaurar_janela(window)),
        pystray.MenuItem('Sair', sair_da_bandeja)
    )
    icone_bandeja = pystray.Icon("Bom Custo", image, "Bom Custo", menu)
    icone_bandeja.on_activate = lambda icon: restaurar_janela(window)
    threading.Thread(target=icone_bandeja.run, daemon=True).start()
