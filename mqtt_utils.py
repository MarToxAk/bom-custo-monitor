import paho.mqtt.client as mqtt
import json
from datetime import datetime, timezone, timedelta

# O callback de conexão

def on_connect(client, userdata, flags, rc):
    # print("Conectado ao MQTT Broker:", MQTT_HOST, "com código", rc)
    client.subscribe("status/status")
    client.subscribe("status/refresh")

# O callback de mensagem

def on_message_factory(dados_ficticios, atualizar_lista_e_botoes, status_cores, status_descricoes, buttons, tocar_som_notificacao, messagebox, abrir_link, parar_som):
    try:
        from winotify import Notification
    except ImportError:
        Notification = None
    def on_message(client, userdata, msg):
        try:
            novo = json.loads(msg.payload.decode())
            try:
                # Sempre armazena datahora em UTC ISO 8601 (com 'Z')
                datahora_utc = datetime.fromisoformat(novo['datahora'].replace("Z", "+00:00"))
                novo['datahora'] = datahora_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                datahora_utc = None
            if isinstance(novo, dict) and all(k in novo for k in ("numero", "nome", "datahora", "status", "chatid", "account_id")):
                if novo["status"] == 8:
                    if datahora_utc is not None:
                        agora_utc = datetime.now(timezone.utc)
                        if (agora_utc - datahora_utc) > timedelta(hours=24):
                            return
                idx_existente = next(
                    (i for i, p in enumerate(dados_ficticios) if str(p["numero"]) == str(novo["numero"])),
                    None
                )
                if idx_existente is not None:
                    del dados_ficticios[idx_existente]
                novo["novo_mqtt"] = True
                dados_ficticios.append(novo)
                novo_btn_idx = atualizar_lista_e_botoes()
                # Notificação winotify para qualquer status
                status_idx = novo["status"] - 1
                cor = status_cores[status_idx]
                url = f"https://chat.autopyweb.com.br/app/accounts/{novo['account_id']}/conversations/{novo['chatid']}"
                if Notification:
                    try:
                        toast = Notification(
                            app_id="StatusMonitor",
                            title=f"Novo status: {status_descricoes[cor]}",
                            msg=f"Pedido {novo['numero']} - {novo['nome']}\nClique para abrir o chat."
                        )
                        toast.add_actions(label="Abrir chat", launch=url)
                        toast.show()
                    except Exception:
                        pass
                # Tocar som junto com a notificação (apenas status 1, 3, 7)
                if novo["status"] in (1, 3, 7):
                    tocar_som_notificacao()
                # NÃO remover destaque do botão aqui!
                # O destaque será removido apenas quando o usuário interagir
        except Exception:
            pass
    return on_message

# Função para criar e iniciar o cliente MQTT

def iniciar_mqtt(on_connect, on_message, host, port):
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(host, port, 60)
    mqtt_client.loop_start()
    return mqtt_client
