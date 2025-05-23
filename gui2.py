import tkinter as tk
from tkinter import PhotoImage, ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import psycopg2
import winsound
import webbrowser
import os
import sys
import urllib.request
import ssl
import requests
import time
from db_utils import buscar_dados_postgres
from ui_utils import ToolTip, formatar_tempo, parar_som, abrir_link
from mqtt_utils import on_connect, on_message_factory, iniciar_mqtt
from config import MQTT_HOST, MQTT_PORT  # (crie config.py se desejar centralizar variáveis)
from tray_utils import minimizar_para_bandeja

APP_VERSION = "1.0.3"

OUTPUT_PATH = Path(__file__).parent
ASSETS_PATH = OUTPUT_PATH / Path(r"\\bot\Programa\Status\build\assets\frame0")

# Caminho de configuração seguro para .exe e script
if getattr(sys, 'frozen', False):
    # Executável (PyInstaller)
    base_dir = os.path.expandvars(r'%APPDATA%')
else:
    # Script normal
    base_dir = os.path.expanduser('~')
config_dir = os.path.join(base_dir, 'StatusMonitor')
os.makedirs(config_dir, exist_ok=True)
CONFIG_FILE = os.path.join(config_dir, 'user_config.json')

def relative_to_assets(path: str) -> Path:
    return ASSETS_PATH / Path(path)

def chave_ordenacao(pedido):
    # Prioridade explícita para status de 1 a 8
    if pedido["status"] == 1:
        prioridade = 0
    elif pedido["status"] == 3:
        prioridade = 1
    elif pedido["status"] == 5:
        prioridade = 2
    elif pedido["status"] == 2:
        prioridade = 3
    elif pedido["status"] == 4:
        prioridade = 4
    elif pedido["status"] == 6:
        prioridade = 5
    elif pedido["status"] == 7:
        prioridade = 6
    elif pedido["status"] == 8:
        prioridade = 7
    else:
        prioridade = 8
    # Corrige o parse da data para aceitar o formato ISO 8601 UTC
    datahora_str = pedido['datahora']
    try:
        # Remove o 'Z' e os milissegundos se existirem
        if datahora_str.endswith('Z'):
            datahora_str = datahora_str[:-1]
        if '.' in datahora_str:
            datahora_str = datahora_str.split('.')[0]
        datahora = datetime.strptime(datahora_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        datahora = datetime.now(timezone.utc)
    return (prioridade, -datahora.timestamp())

def salvar_config():
    config = {
        'tocar_som': tocar_som,
        'som_personalizado': som_personalizado,
        'modo_escuro': modo_escuro
    }
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f)

def carregar_config():
    global tocar_som, som_personalizado, modo_escuro
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            tocar_som = config.get('tocar_som', True)
            som_personalizado = config.get('som_personalizado', None)
            modo_escuro = config.get('modo_escuro', True)
    # Atualiza o menu e interface conforme config carregada
    if tocar_som:
        som_menu.entryconfig(0, label="Desabilitar som de notificação")
    else:
        som_menu.entryconfig(0, label="Habilitar som de notificação")
    if som_personalizado:
        som_menu.entryconfig(2, label=f"Som: {os.path.basename(som_personalizado)}")
    else:
        som_menu.entryconfig(2, label="Som: padrão do sistema")
    # Corrige: só chama alternar_tema se o valor salvo for diferente do atual
    if modo_escuro != (window['bg'] == '#2C2C2C'):
        alternar_tema()
    else:
        atualizar_lista_e_botoes()

def atualizar_lista_e_botoes():
    """
    Atualiza a lista de pedidos na interface e os botões de ação.
    Exibe mensagens de erro se necessário.
    """
    global dados_ficticios
    try:
        if isinstance(dados_ficticios, dict):
            if "dados" in dados_ficticios:
                dados_ficticios = dados_ficticios["dados"]
            else:
                dados_ficticios = []
        if not isinstance(dados_ficticios, list):
            dados_ficticios = []
        dados_ficticios.sort(key=chave_ordenacao)
        # Remove todos os widgets do frame (botões e labels de separação)
        for widget in scrollable_frame.winfo_children():
            widget.destroy()
        buttons.clear()
        color_images.clear()
        # Agrupamento visual por status
        ultimo_status = None
        status_labels = {}
        novo_btn_idx = None
        tem_novo = False
        agora = datetime.now()
        for idx, pedido in enumerate(dados_ficticios):
            # Filtrar status 8 para exibir apenas até 24h
            if pedido["status"] == 8:
                datahora_pedido = pedido['datahora']
                try:
                    if datahora_pedido.endswith('Z'):
                        datahora_pedido = datahora_pedido[:-1]
                    if '.' in datahora_pedido:
                        datahora_pedido = datahora_pedido.split('.')[0]
                    datahora_pedido_dt = datetime.strptime(datahora_pedido, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                except Exception:
                    datahora_pedido_dt = datetime.now(timezone.utc)
                agora_utc = datetime.now(timezone.utc)
                if (agora_utc - datahora_pedido_dt).total_seconds() > 86400:
                    continue  # pula pedidos entregues com mais de 24h
            status_idx = pedido["status"] - 1
            cor = status_cores[status_idx]
            # Adiciona separador/título de grupo se mudou o status
            if pedido["status"] != ultimo_status:
                if pedido["status"] not in status_labels:
                    # Ajuste de cor do fundo do label conforme tema
                    if modo_escuro:
                        bg_label = "#232323"
                        fg_label = cor
                    else:
                        bg_label = "#E9E9E9"
                        fg_label = cor
                    label = tk.Label(
                        scrollable_frame,
                        text=status_descricoes[cor],
                        bg=bg_label,
                        fg=fg_label,
                        font=("Inter SemiBold", 11, "bold"),
                        anchor="w",
                        padx=8
                    )
                    label.pack(fill="x", pady=(10, 2), padx=4)
                    status_labels[pedido["status"]] = label
                ultimo_status = pedido["status"]
            img = PhotoImage(width=20, height=20)
            for x in range(20):
                for y in range(20):
                    if (x - 10) ** 2 + (y - 10) ** 2 <= 100:
                        img.put(cor, (x, y))
            color_images.append(img)
            datahora_pedido = pedido['datahora']
            # Corrige o parse da data para aceitar o formato ISO 8601
            try:
                if datahora_pedido.endswith('Z'):
                    datahora_pedido = datahora_pedido[:-1]
                if '.' in datahora_pedido:
                    datahora_pedido = datahora_pedido.split('.')[0]
                datahora_pedido_dt = datetime.strptime(datahora_pedido, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            except Exception:
                datahora_pedido_dt = datetime.now(timezone.utc)
            diff = datetime.now(timezone.utc) - datahora_pedido_dt
            primeiro_nome = pedido['nome'].split()[0]
            texto = f"{pedido['numero']} - {primeiro_nome} - {formatar_tempo(diff)}"
            style_btn = "Novo.TButton" if pedido.get("novo_mqtt") else "Rounded.TButton"
            click_count = {'count': 0}  # contador de cliques por botão
            def on_pedido_click(p=pedido, btn_idx=idx):
                click_count['count'] += 1
                if click_count['count'] == 1:
                    parar_som()  # não passa btn, assim não muda o estilo
                else:
                    parar_som()
                    webbrowser.open(
                        f"https://chat.autopyweb.com.br/app/accounts/{p['account_id']}/conversations/{p['chatid']}",
                        new=0
                    )
                    click_count['count'] = 0  # reseta para permitir novo ciclo
            button = ttk.Button(
                scrollable_frame,
                text=texto,
                image=img,
                compound="left",
                style=style_btn,
                command=on_pedido_click
            )
            button.bind("<Enter>", lambda e, btn=button: parar_som(btn=btn))
            button.pack(fill="x", pady=4, padx=16)
            ToolTip(button, status_descricoes[cor])
            buttons.append(button)
            if pedido.get("novo_mqtt"):
                novo_btn_idx = idx
                tem_novo = True
        # Notificação persistente: se houver novo pedido, inicia loop de som
        if tem_novo:
            if not notificacao_ativa:
                tocar_som_persistente()
        else:
            parar_som()
        return novo_btn_idx
    except Exception as e:
        messagebox.showerror("Erro na atualização da lista", f"Erro ao atualizar a lista de pedidos: {e}")
        return None

def atualizar_dados_periodicamente():
    """
    Atualiza os dados de pedidos automaticamente a cada 30 minutos.
    """
    global dados_ficticios
    novos_dados = buscar_dados_postgres()
    if isinstance(novos_dados, dict) and "dados" in novos_dados:
        novos_dados = novos_dados["dados"]
    elif not isinstance(novos_dados, list):
        novos_dados = []
    if not isinstance(dados_ficticios, list):
        dados_ficticios = []
    if novos_dados != dados_ficticios:
        dados_ficticios.clear()
        dados_ficticios.extend(novos_dados)
        atualizar_lista_e_botoes()
    window.after(1800000, atualizar_dados_periodicamente)  # 30 minutos

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

# Estilo ttk para botões arredondados e alerta
window = tk.Tk()
window.title("Bom Custo - Monitoramento de Produção")
# Para definir um ícone personalizado, coloque o arquivo bomcusto.ico na mesma pasta e descomente a linha abaixo:
# window.iconbitmap("bomcusto.ico")
window.geometry("328x418")
window.configure(bg="#2C2C2C")  # Cinza chumbo

titulo = tk.Label(window, text="Status de Produção", bg="#2C2C2C", fg="#FFFFFF", font=("Inter SemiBold", 16))
titulo.pack(pady=(10, 0))

style = ttk.Style(window)

# Defina o tema clam para melhor suporte a cor de fundo
style.theme_use('clam')

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
style.configure(
    "Novo.TButton",
    background="#FFB6B6",  # Vermelho claro
    foreground="black",
    font=("Inter SemiBold", 12),
    borderwidth=0,
    focusthickness=3,
    focuscolor='none',
    padding=8,
    relief="flat"
)
style.map(
    "Novo.TButton",
    background=[("active", "#FF7F7F")],  # Vermelho mais forte ao passar o mouse
    foreground=[("active", "black")]
)

# Variável global para controle do som
tocar_som = True
som_personalizado = None

# --- Notificação persistente ---
notificacao_ativa = False
notificacao_after_id = None

def tocar_som_persistente():
    global notificacao_ativa, notificacao_after_id
    if not tocar_som:
        return
    notificacao_ativa = True
    if som_personalizado:
        winsound.PlaySound(som_personalizado, winsound.SND_FILENAME | winsound.SND_ASYNC)
    else:
        winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
    # Agenda o próximo toque se ainda não foi parado
    if notificacao_ativa:
        notificacao_after_id = window.after(2000, tocar_som_persistente)  # repete a cada 2s

def parar_som(btn=None):
    global notificacao_ativa, notificacao_after_id
    notificacao_ativa = False
    winsound.PlaySound(None, winsound.SND_PURGE)
    if notificacao_after_id:
        window.after_cancel(notificacao_after_id)
        notificacao_after_id = None
    # Se for passado um botão, pode mudar o estilo ou fazer highlight, se desejar

def toggle_som():
    global tocar_som
    tocar_som = not tocar_som
    if tocar_som:
        som_menu.entryconfig(0, label="Desabilitar som de notificação")
    else:
        som_menu.entryconfig(0, label="Habilitar som de notificação")
    salvar_config()

def escolher_som():
    global som_personalizado
    arquivo = filedialog.askopenfilename(
        title="Selecione um arquivo de som (.wav)",
        filetypes=[("Arquivos WAV", "*.wav")]
    )
    if arquivo:
        som_personalizado = arquivo
        som_menu.entryconfig(2, label=f"Som: {arquivo.split('/')[-1]}")
    else:
        som_personalizado = None
        som_menu.entryconfig(2, label="Som: padrão do sistema")
    salvar_config()

# Suporte a tema claro/escuro
modo_escuro = True

def alternar_tema():
    global modo_escuro
    modo_escuro = not modo_escuro
    if modo_escuro:
        window.configure(bg="#2C2C2C")
        titulo.configure(bg="#2C2C2C", fg="#FFFFFF")
        frame_principal.configure(bg="#2C2C2C")
        canvas.configure(bg="#2C2C2C")
        scrollable_frame.configure(bg="#2C2C2C")
        style.configure("Rounded.TButton", background="#FFFFFF", foreground="black")
        style.map("Rounded.TButton", background=[("active", "#F5F5F5")], foreground=[("active", "black")])
        style.configure("Alerta.TButton", background="#FFFACD", foreground="black")
        style.map("Alerta.TButton", background=[("active", "#FFFACD")], foreground=[("active", "black")])
        style.configure("Novo.TButton", background="#FFB6B6", foreground="black")
        style.map("Novo.TButton", background=[("active", "#FF7F7F")], foreground=[("active", "black")])
        som_menu.entryconfig(1, label="Tema claro")
    else:
        window.configure(bg="#F5F5F5")
        titulo.configure(bg="#F5F5F5", fg="#222222")
        frame_principal.configure(bg="#F5F5F5")
        canvas.configure(bg="#F5F5F5")
        scrollable_frame.configure(bg="#F5F5F5")
        style.configure("Rounded.TButton", background="#222222", foreground="#FFFFFF")
        style.map("Rounded.TButton", background=[("active", "#444444")], foreground=[("active", "#FFFFFF")])
        style.configure("Alerta.TButton", background="#FFFACD", foreground="#222222")
        style.map("Alerta.TButton", background=[("active", "#FFE066")], foreground=[("active", "#222222")])
        style.configure("Novo.TButton", background="#FFB6B6", foreground="#222222")
        style.map("Novo.TButton", background=[("active", "#FF7F7F")], foreground=[("active", "#222222")])
        som_menu.entryconfig(1, label="Tema escuro")
    salvar_config()
    atualizar_lista_e_botoes()

# Função para verificar atualização
def verificar_atualizacao():
    url = "https://n8n.autopyweb.com.br/webhook/d3b516dd-7874-4360-8e0f-637eb74f2b14"
    try:
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(url, context=context, timeout=5) as response:
            data = response.read().decode()
            import json as _json
            remote = _json.loads(data)
            remote_version = remote.get("APP_VERSION", "0.0.0")
            download_url = remote.get("DOWNLOAD_URL", "https://autopyweb.com.br/update/StatusMonitor.exe")
            if remote_version > APP_VERSION:
                # Atualização obrigatória: não pergunta ao usuário
                import tempfile
                import subprocess
                temp_dir = tempfile.gettempdir()
                installer_path = os.path.join(temp_dir, "StatusMonitor_update.exe")
                try:
                    with urllib.request.urlopen(download_url, context=context) as dl, open(installer_path, 'wb') as out:
                        out.write(dl.read())
                    messagebox.showinfo("Atualização obrigatória", f"Nova versão disponível: {remote_version}\nO sistema será atualizado agora.")
                    # Removido /VERYSILENT para mostrar o instalador ao usuário
                    window.after(1000, lambda: subprocess.Popen([installer_path], shell=True))
                    window.after(2000, window.destroy)
                except Exception as e:
                    messagebox.showerror("Erro ao baixar instalador", str(e))
        # Não exibe mensagem se já está na versão mais recente
    except Exception as e:
        messagebox.showerror("Erro ao verificar atualização", str(e))

# Função para exibir informações sobre o sistema
def mostrar_sobre():
    messagebox.showinfo(
        "Sobre o Bom Custo",
        "Bom Custo - Monitoramento de Produção\nVersão: {}\n\nSistema de monitoramento de status de pedidos com integração PostgreSQL e MQTT.\n\nDesenvolvido para: Gráfica Bom Custo\nContato: suporte@autopyweb.com.br\n\nPara atualizações e suporte, acesse:\nhttps://autopyweb.com.br"
        .format(APP_VERSION)
    )

# Menu para controle do som, tema e ajuda
top_menu = tk.Menu(window)
som_menu = tk.Menu(top_menu, tearoff=0)
som_menu.add_command(label="Desabilitar som de notificação", command=toggle_som)
som_menu.add_command(label="Tema claro", command=alternar_tema)
som_menu.add_command(label="Som: padrão do sistema", command=escolher_som)
top_menu.add_cascade(label="Opções", menu=som_menu)

# Adiciona menu Ajuda/Sobre
ajuda_menu = tk.Menu(top_menu, tearoff=0)
ajuda_menu.add_command(label="Sobre", command=mostrar_sobre)
top_menu.add_cascade(label="Ajuda", menu=ajuda_menu)

window.config(menu=top_menu)

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

carregando_label = tk.Label(window, text="Carregando...", bg="#2C2C2C", fg="#FFFFFF", font=("Inter", 12, "italic"))
carregando_label.pack(pady=20)
window.update()

def buscar_dados_postgres():
    """
    Busca os dados de pedidos via API (sem autenticação JWT).
    Retorna uma lista de pedidos ou lista vazia em caso de erro.
    """
    url = "https://n8n.autopyweb.com.br/webhook/41ce2ba0-9fc3-4ebb-852b-7c8714048bdf"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        try:
            dados = response.json()
            if isinstance(dados, dict) and "dados" in dados:
                return dados["dados"]
            return dados
        except Exception:
            return []
    except Exception as e:
        messagebox.showerror("Erro ao buscar dados", f"Não foi possível buscar os dados: {e}")
        return []

dados_ficticios = buscar_dados_postgres()
if isinstance(dados_ficticios, dict):
    # Se ainda vier dict, tenta extrair a lista da chave correta
    if "dados" in dados_ficticios:
        dados_ficticios = dados_ficticios["dados"]
    else:
        # Se não houver chave 'dados', transforma em lista vazia para evitar erro
        dados_ficticios = []
carregando_label.destroy()
buttons = []
color_images = []
carregar_config()  # <-- Agora é seguro chamar aqui, após definir buttons/color_images e carregar dados
atualizar_lista_e_botoes()
atualizar_dados_periodicamente()

# Ajuste na chamada do winsound para respeitar o toggle
def tocar_som_notificacao():
    # Compatibilidade: dispara notificação persistente
    if not notificacao_ativa:
        tocar_som_persistente()

# Inicialização do MQTT
mqtt_client = iniciar_mqtt(
    on_connect,
    on_message_factory(dados_ficticios, atualizar_lista_e_botoes, status_cores, status_descricoes, buttons, tocar_som_notificacao, messagebox, abrir_link, parar_som),
    MQTT_HOST,
    MQTT_PORT
)

# Atualização dinâmica dos tempos
def atualizar_tempos():
    agora_utc = datetime.now(timezone.utc)
    for i, pedido in enumerate(dados_ficticios):
        if i >= len(buttons):
            break  # Evita IndexError se buttons for menor
        datahora_pedido = pedido['datahora']
        try:
            if datahora_pedido.endswith('Z'):
                datahora_pedido = datahora_pedido[:-1]
            if '.' in datahora_pedido:
                datahora_pedido = datahora_pedido.split('.')[0]
            datahora_pedido_dt = datetime.strptime(datahora_pedido, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            datahora_pedido_dt = agora_utc
        diff = agora_utc - datahora_pedido_dt
        primeiro_nome = pedido['nome'].split()[0]
        texto = f"{pedido['numero']} - {primeiro_nome} - {formatar_tempo(diff)}"
        buttons[i].config(text=texto)
    window.after(60000, atualizar_tempos)

atualizar_tempos()

# Vincula evento de minimizar
window.bind('<Unmap>', lambda e: minimizar_para_bandeja(window, messagebox, on_closing) if window.state() == 'iconic' else None)

# Confirmação ao fechar a janela
def on_closing():
    salvar_config()
    if messagebox.askokcancel("Sair", "Deseja realmente fechar o sistema?"):
        window.destroy()
window.protocol("WM_DELETE_WINDOW", on_closing)

window.resizable(False, False)
# Chama a verificação de atualização automaticamente ao iniciar o app
window.after(1000, verificar_atualizacao)
window.mainloop()
