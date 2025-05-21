import tkinter as tk
from tkinter import PhotoImage, ttk
from pathlib import Path
from datetime import datetime
import paho.mqtt.client as mqtt
import json
import winsound
import webbrowser
import psycopg2
from tkinter import Tk, Canvas, Entry, Text, Button, PhotoImage

OUTPUT_PATH = Path(__file__).parent
ASSETS_PATH = OUTPUT_PATH / Path(r"\\bot\Programa\Status\build\assets\frame0")

def relative_to_assets(path: str) -> Path:
    return ASSETS_PATH / Path(path)

# MQTT Config
MQTT_HOST = "tt.autopyweb.com.br"
MQTT_PORT = 1883

def on_connect(client, userdata, flags, rc):
    print("Conectado ao MQTT Broker:", MQTT_HOST, "com código", rc)
    client.subscribe("status/status")
    client.subscribe("status/refresh")  # Novo tópico para atualizar tudo

def on_message(client, userdata, msg):
    print(f"Mensagem recebida no tópico {msg.topic}: {msg.payload.decode()}")
    if msg.topic == "status/refresh":
        atualizar_tudo()
        return
    try:
        novo = json.loads(msg.payload.decode())
        try:
            # Tenta converter ISO para o formato desejado
            datahora_pedido = datetime.fromisoformat(novo['datahora'].replace("Z", "+00:00"))
            novo['datahora'] = datahora_pedido.strftime("%Y-%m-%d %H:%M")
        except Exception:
            # Se já estiver no formato correto, só segue
            pass
        if isinstance(novo, dict) and all(k in novo for k in ("numero", "nome", "datahora", "status", "chatid", "account_id")):
            # Verifica se já existe um pedido com o mesmo número
            idx_existente = next((i for i, p in enumerate(dados_ficticios) if p["numero"] == novo["numero"]), None)
            status_idx = novo["status"] - 1
            cor = status_cores[status_idx]
            img = PhotoImage(width=20, height=20)
            img.put("{#FFFFFF}", to=(0, 0, 20, 20))
            for x in range(20):
                for y in range(20):
                    if (x - 10) ** 2 + (y - 10) ** 2 <= 100:
                        img.put(cor, (x, y))
            datahora_pedido = datetime.strptime(novo['datahora'], "%Y-%m-%d %H:%M")
            diff = datetime.now() - datahora_pedido
            horas = diff.seconds // 3600 + diff.days * 24
            minutos = (diff.seconds // 60) % 60
            primeiro_nome = novo['nome'].split()[0]
            texto = f"{novo['numero']} - {primeiro_nome} - {horas:02d}:{minutos:02d}"

            def parar_som(event=None, btn=None):
                winsound.PlaySound(None, winsound.SND_PURGE)
                if btn:
                    btn.config(style="Rounded.TButton")

            if idx_existente is not None:
                # Atualiza os dados e o botão existente
                dados_ficticios[idx_existente] = novo
                color_images[idx_existente] = img
                buttons[idx_existente].config(
                    text=texto,
                    image=img,
                    style="Alerta.TButton",
                    command=lambda acc=novo['account_id'], chat=novo['chatid']:
                        (parar_som(btn=buttons[idx_existente]), webbrowser.open(f"https://chat.autopyweb.com.br/app/accounts/{acc}/conversations/{chat}"))
                )
                ToolTip(buttons[idx_existente], status_descricoes[cor])
                if novo["status"] in (1, 3, 7):
                    winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_LOOP)
            else:
                # Adiciona novo botão normalmente
                color_images.insert(0, img)
                button = ttk.Button(
                    scrollable_frame,
                    text=texto,
                    image=img,
                    compound="left",
                    style="Alerta.TButton",
                    command=lambda acc=novo['account_id'], chat=novo['chatid']:
                        (parar_som(btn=button), webbrowser.open(f"https://chat.autopyweb.com.br/app/accounts/{acc}/conversations/{chat}"))
                )
                button.bind("<Enter>", lambda e, btn=button: parar_som(btn=btn))
                if buttons:
                    button.pack(fill="x", pady=4, padx=8, before=buttons[0])
                else:
                    button.pack(fill="x", pady=4, padx=8)
                ToolTip(button, status_descricoes[cor])
                buttons.insert(0, button)
                dados_ficticios.insert(0, novo)
                if novo["status"] in (1, 3, 7):
                    winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_LOOP)
        else:
            print("Recebido número simples ou formato inesperado:", novo)
    except Exception as e:
        print("Erro ao adicionar novo pedido via MQTT:", e)

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
mqtt_client.loop_start()

def buscar_dados_postgres():
    conn = psycopg2.connect(
        host="tt.autopyweb.com.br",
        database="grafica",
        user="chatwoot",
        password="vnailU4zTkcPPg6"
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            p.numero, 
            p.nome, 
            sh.datahora, 
            sh.status, 
            p.chatid, 
            p.account_id
        FROM pedidos p
        JOIN (
            SELECT DISTINCT ON (pedido_id) *
            FROM status_historico
            ORDER BY pedido_id, datahora DESC
        ) sh ON sh.pedido_id = p.id
        ORDER BY sh.datahora DESC
        LIMIT 50
    """)
    resultados = []
    for row in cur.fetchall():
        resultados.append({
            "numero": row[0],
            "nome": row[1],
            "datahora": row[2].strftime("%Y-%m-%d %H:%M"),
            "status": row[3],
            "chatid": row[4],
            "account_id": row[5],
        })
    cur.close()
    conn.close()
    return resultados

# Cores e descrições
status_cores = [
    "#0080FF",  # 1 Azul
    "#FFCC00",  # 2 Amarelo
    "#00CC66",  # 3 Verde
    "#FF8C00",  # 4 Laranja
    "#FF3333",  # 5 Vermelho
    "#9933FF",  # 6 Roxo
    "#D9D9D9",  # 7 Cinza Claro
    "#8B4513",  # 8 Marrom
]
status_descricoes = {
    "#0080FF": "Solicitação Recebida",
    "#FFCC00": "Arte em Desenvolvimento",
    "#00CC66": "Arte Aprovada",
    "#FF8C00": "Preparação de Materiais",
    "#FF3333": "Impressão em Andamento",
    "#9933FF": "Acabamento e Finalização",
    "#D9D9D9": "Pronto para Retirada/Entrega",
    "#8B4513": "Entregue"
}

# ToolTip
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
        label = tk.Label(tw, text=self.text, background="#FFFFE0", relief="solid", borderwidth=1, font=("tahoma", "10", "normal"))
        label.pack(ipadx=4)
    def hide_tip(self, event=None):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

# Estilo ttk para botões arredondados e alerta
window = tk.Tk()
window.geometry("328x418")
window.configure(bg="#2C2C2C")  # Cinza chumbo
titulo = tk.Label(window, text="Status de Produção", bg="#2C2C2C", fg="#FFFFFF", font=("Inter SemiBold", 16))
titulo.pack(pady=(10, 0))

style = ttk.Style(window)
style.configure(
    "Rounded.TButton",
    background="#FFFFFF",
    foreground="black",
    font=("Inter SemiBold", 12),
    borderwidth=0,
    focusthickness=3,
    focuscolor='none',
    padding=8,
    relief="flat"
)
style.map(
    "Rounded.TButton",
    background=[("active", "#F5F5F5")]
)
style.configure(
    "Alerta.TButton",
    background="#FFFACD",
    foreground="black",
    font=("Inter SemiBold", 12),
    borderwidth=0,
    focusthickness=3,
    focuscolor='none',
    padding=8,
    relief="flat"
)
style.map(
    "Alerta.TButton",
    background=[("active", "#FFFACD")]
)

# Frame principal e canvas com scroll
frame_principal = tk.Frame(window, bg="#2C2C2C")
frame_principal.pack(fill="both", expand=True)
canvas = tk.Canvas(frame_principal, bg="#2C2C2C", highlightthickness=0)
canvas.pack(side="left", fill="both", expand=True)
scrollbar = tk.Scrollbar(frame_principal, orient="vertical", command=canvas.yview)
scrollbar.pack(side="right", fill="y")
scrollable_frame = tk.Frame(canvas, bg="#2C2C2C")

def on_frame_configure(event):
    canvas.configure(scrollregion=canvas.bbox("all"))

scrollable_frame.bind("<Configure>", on_frame_configure)
window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

def resize_canvas(event):
    canvas.itemconfig(window_id, width=event.width)

canvas.bind("<Configure>", resize_canvas)
canvas.configure(yscrollcommand=scrollbar.set)

def _on_mousewheel(event):
    canvas.yview_scroll(int(-1*(event.delta/120)), "units")

canvas.bind_all("<MouseWheel>", _on_mousewheel)

# Busca dados do banco
dados_ficticios = buscar_dados_postgres()

# Criação dinâmica dos botões
buttons = []
color_images = []
for i, pedido in enumerate(dados_ficticios):
    status_idx = pedido["status"] - 1
    cor = status_cores[status_idx]
    img = PhotoImage(width=20, height=20)
    img.put("{#FFFFFF}", to=(0, 0, 20, 20))
    for x in range(20):
        for y in range(20):
            if (x - 10) ** 2 + (y - 10) ** 2 <= 100:
                img.put(cor, (x, y))
    color_images.append(img)
    datahora_pedido = datetime.strptime(pedido['datahora'], "%Y-%m-%d %H:%M")
    diff = datetime.now() - datahora_pedido
    horas = diff.seconds // 3600 + diff.days * 24
    minutos = (diff.seconds // 60) % 60
    primeiro_nome = pedido['nome'].split()[0]
    texto = f"{pedido['numero']} - {primeiro_nome} - {horas:02d}:{minutos:02d}"
    button = ttk.Button(
        scrollable_frame,
        text=texto,
        image=img,
        compound="left",
        style="Rounded.TButton",
        command=lambda acc=pedido['account_id'], chat=pedido['chatid']:
            webbrowser.open(f"https://chat.autopyweb.com.br/app/accounts/{acc}/conversations/{chat}")
    )
    button.pack(fill="x", pady=4, padx=8)
    ToolTip(button, status_descricoes[cor])
    buttons.append(button)

# Atualização dinâmica dos tempos
def atualizar_tempos():
    agora = datetime.now()
    for i, pedido in enumerate(dados_ficticios):
        datahora_pedido = datetime.strptime(pedido['datahora'], "%Y-%m-%d %H:%M")
        diff = agora - datahora_pedido
        horas = diff.seconds // 3600 + diff.days * 24
        minutos = (diff.seconds // 60) % 60
        primeiro_nome = pedido['nome'].split()[0]
        texto = f"{pedido['numero']} - {primeiro_nome} - {horas:02d}:{minutos:02d}"
        buttons[i].config(text=texto)
    window.after(60000, atualizar_tempos)

def atualizar_tudo():
    global dados_ficticios, buttons, color_images
    # Remove todos os botões antigos
    for btn in buttons:
        btn.destroy()
    buttons.clear()
    color_images.clear()
    # Recarrega os dados do banco
    dados_ficticios = buscar_dados_postgres()
    # Redesenha os botões
    for i, pedido in enumerate(dados_ficticios):
        status_idx = pedido["status"] - 1
        cor = status_cores[status_idx]
        img = PhotoImage(width=20, height=20)
        img.put("{#FFFFFF}", to=(0, 0, 20, 20))
        for x in range(20):
            for y in range(20):
                if (x - 10) ** 2 + (y - 10) ** 2 <= 100:
                    img.put(cor, (x, y))
        color_images.append(img)
        datahora_pedido = datetime.strptime(pedido['datahora'], "%Y-%m-%d %H:%M")
        diff = datetime.now() - datahora_pedido
        horas = diff.seconds // 3600 + diff.days * 24
        minutos = (diff.seconds // 60) % 60
        primeiro_nome = pedido['nome'].split()[0]
        texto = f"{pedido['numero']} - {primeiro_nome} - {horas:02d}:{minutos:02d}"

        button = ttk.Button(
            scrollable_frame,
            text=texto,
            image=img,
            compound="left",
            style="Rounded.TButton",
            command=lambda acc=pedido['account_id'], chat=pedido['chatid']:
                webbrowser.open(f"https://chat.autopyweb.com.br/app/accounts/{acc}/conversations/{chat}")
        )
        button.pack(fill="x", pady=4, padx=8)
        ToolTip(button, status_descricoes[cor])
        buttons.append(button)

atualizar_tempos()
window.resizable(False, False)
window.mainloop()
