import psycopg2
from datetime import datetime, timezone, timedelta

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
    agora = datetime.now(timezone(timedelta(hours=-3)))
    for row in cur.fetchall():
        # Supondo que row[2] está em UTC
        datahora_utc = row[2].replace(tzinfo=timezone.utc)
        datahora_brasilia = datahora_utc.astimezone(timezone(timedelta(hours=-3)))
        status = row[3]
        # Filtro: status 8 só aparece se for das últimas 12h
        if status == 8:
            if (agora - datahora_brasilia) > timedelta(hours=12):
                continue
        resultados.append({
            "numero": row[0],
            "nome": row[1],
            "datahora": datahora_brasilia.strftime("%Y-%m-%d %H:%M"),
            "status": status,
            "chatid": row[4],
            "account_id": row[5]
        })
    cur.close()
    conn.close()
    print("[DEBUG] Pedidos carregados:")
    for pedido in resultados:
        print(pedido)
    return resultados
