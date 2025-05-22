import webbrowser
import winsound
from tkinter import messagebox
from datetime import datetime
import tkinter as tk

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)
    def show_tip(self, event=None):
        if self.tipwindow or not self.text:
            return
        x, y, _, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 40
        y = y + cy + self.widget.winfo_rooty() + 10
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, background="#FFFFE0", relief="solid", borderwidth=1, font="tahoma 10 normal")
        label.pack(ipadx=4)
    def hide_tip(self, event=None):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

def formatar_tempo(diff):
    dias = diff.days
    horas = diff.seconds // 3600
    minutos = (diff.seconds // 60) % 60
    if dias > 0:
        return f"{dias}d {horas:02d}:{minutos:02d}"
    else:
        return f"{horas:02d}:{minutos:02d}"

def parar_som(btn=None, event=None):
    """
    Para o som de notificação. Se um botão for passado, pode alterar o estilo.
    A ordem dos parâmetros foi ajustada para compatibilidade com gui2.py.
    """
    winsound.PlaySound(None, winsound.SND_PURGE)
    if btn:
        btn.config(style="Alerta.TButton")

def abrir_link(url):
    webbrowser.open(url, new=2)
