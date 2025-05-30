import win32print
import tempfile
import subprocess
from tkinter import messagebox
import qrcode
from io import BytesIO
from PIL import Image

def imprimir_pedido_termica(pedido, impressora_termica, metodo_impressao_termica, modo_impressao, status_descricoes, status_cores, salvar_config):
    if not impressora_termica:
        return
    # Verifica se a impressora ainda existe
    try:
        flags = win32print.PRINTER_ENUM_CONNECTIONS | win32print.PRINTER_ENUM_LOCAL
        impressoras = [printer[2] for printer in win32print.EnumPrinters(flags)]
        if impressora_termica not in impressoras:
            messagebox.showerror("Impressora não encontrada", f"A impressora térmica selecionada ('{impressora_termica}') não está mais disponível. Selecione novamente em Opções > Selecionar impressora térmica.")
            salvar_config()
            return
    except Exception:
        pass
    # Apenas imprime se o modo e status forem compatíveis
    if modo_impressao == "Orçamento" and pedido["status"] != 1:
        return
    if modo_impressao == "Produção" and pedido["status"] != 3:
        return
    if modo_impressao == "Usuário":
        return
    # Gera a URL do QR Code de acordo com o status recebido
    if pedido["status"] == 1:
        qr_status = 3
    elif pedido["status"] == 3:
        qr_status = 8
    else:
        qr_status = pedido["status"]
    url_qr = f"https://autopyweb.com.br/grafica/atualizacao.html?numero={pedido['numero']}&status={qr_status}"
    # Gera o QR Code como imagem (box_size maior para aumentar o QR)
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url_qr)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")
    # Salva a imagem do QR em um buffer
    buffer = BytesIO()
    img_qr.save(buffer, format="PNG")
    qr_bytes = buffer.getvalue()
    buffer.close()
    # Gera o QR Code em ASCII para impressoras térmicas Bematech
    try:
        from io import StringIO
        import sys
        old_stdout = sys.stdout
        sys.stdout = qr_ascii = StringIO()
        # Gera o QRCode ASCII a partir do objeto qr (maior box_size já reflete no ASCII)
        qr.print_ascii(tty=False, invert=True)
        sys.stdout = old_stdout
        qr_ascii_str = qr_ascii.getvalue()
    except Exception as e:
        qr_ascii_str = "[QR não disponível]"
    texto = (
        f"Pedido: {pedido['numero']}\nCliente: {pedido['nome']}\nStatus: {status_descricoes.get(status_cores[pedido['status']-1],'')}\nData: {pedido['datahora']}\n"
        "\nLeia este QR Code para atualizar o status correspondente.\n"
        "\n"
    )
    # Comando ESC/POS para QR Code
    def escpos_qrcode(data):
        # ESC/POS QR: https://reference.epson-biz.com/modules/ref_escpos/index.php?content_id=140
        store_len = len(data) + 3
        pL = store_len % 256
        pH = store_len // 256
        cmds = b''
        # [1] Set QR code model
        cmds += b'\x1D\x28\x6B\x04\x00\x31\x41\x32\x00'
        # [2] Set QR code size (14 = 14 dots/module)
        cmds += b'\x1D\x28\x6B\x03\x00\x31\x43\x0E'
        # [3] Set error correction level (48 = L, 49 = M, 50 = Q, 51 = H)
        cmds += b'\x1D\x28\x6B\x03\x00\x31\x45\x31'
        # [4] Store data
        cmds += b'\x1D\x28\x6B' + bytes([pL, pH]) + b'\x31\x50\x30' + data.encode('utf-8')
        # [5] Print QR code
        cmds += b'\x1D\x28\x6B\x03\x00\x31\x51\x30'
        return cmds
    if metodo_impressao_termica == "win32print":
        try:
            hprinter = win32print.OpenPrinter(impressora_termica)
            try:
                job = win32print.StartDocPrinter(hprinter, 1, ("Status Pedido", None, "RAW"))
                win32print.StartPagePrinter(hprinter)
                win32print.WritePrinter(hprinter, texto.encode("utf-8"))
                # Envia comando ESC/POS para QR Code
                try:
                    escpos_cmd = escpos_qrcode(url_qr)
                    win32print.WritePrinter(hprinter, escpos_cmd)
                except Exception as e:
                    print(f"[LOG] Falha ao enviar ESC/POS QRCode: {e}")
                win32print.EndPagePrinter(hprinter)
                win32print.EndDocPrinter(hprinter)
            finally:
                win32print.ClosePrinter(hprinter)
        except Exception as e:
            messagebox.showerror("Erro de Impressão", f"Erro ao imprimir: {e}")
    elif metodo_impressao_termica == "arquivo_txt":
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as f:
                f.write(texto)
                temp_path = f.name
            subprocess.Popen(["notepad.exe", "/p", temp_path], shell=False)
        except Exception as e:
            messagebox.showerror("Erro de Impressão (arquivo txt)", f"Erro ao imprimir via arquivo txt: {e}")

def testar_impressao_termica(impressora_termica, metodo_impressao_termica):
    if not impressora_termica:
        messagebox.showwarning("Impressora não selecionada", "Selecione uma impressora térmica em Opções > Selecionar impressora térmica.")
        return
    texto = (
        "*** TESTE DE IMPRESSÃO TÉRMICA ***\n"
        f"Impressora: {impressora_termica}\n"
        f"Método: {metodo_impressao_termica}\n"
        "--------------------------\n"
        "Pedido: 12345\nCliente: Teste\nStatus: Teste\nData: 2025-05-29T12:00:00\n"
        "--------------------------\n"
        "Se este texto saiu corretamente, a configuração está OK.\n"
    )
    if metodo_impressao_termica == "win32print":
        try:
            hprinter = win32print.OpenPrinter(impressora_termica)
            try:
                job = win32print.StartDocPrinter(hprinter, 1, ("Teste Impressão", None, "RAW"))
                win32print.StartPagePrinter(hprinter)
                win32print.WritePrinter(hprinter, texto.encode("utf-8"))
                win32print.EndPagePrinter(hprinter)
                win32print.EndDocPrinter(hprinter)
            finally:
                win32print.ClosePrinter(hprinter)
            messagebox.showinfo("Teste de Impressão", "Comando de impressão enviado para a impressora térmica.")
        except Exception as e:
            messagebox.showerror("Erro de Impressão", f"Erro ao imprimir teste: {e}")
    elif metodo_impressao_termica == "arquivo_txt":
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as f:
                f.write(texto)
                temp_path = f.name
            subprocess.Popen(["notepad.exe", "/p", temp_path], shell=False)
            messagebox.showinfo("Teste de Impressão", "Arquivo de teste enviado para impressão via Notepad.")
        except Exception as e:
            messagebox.showerror("Erro de Impressão (arquivo txt)", f"Erro ao imprimir teste: {e}")
