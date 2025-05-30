import win32print
import tempfile
import subprocess
from tkinter import messagebox
import qrcode
from io import BytesIO
from PIL import Image
import logging

logging.basicConfig(filename='impressao_termica.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

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
    qr = qrcode.QRCode(box_size=14, border=2)  # Aumentado para 14
    qr.add_data(url_qr)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")
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
    except Exception:
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
        if getattr(escpos_qrcode, 'use_255', False):
            pL = store_len % 255
            pH = store_len // 255
        else:
            pL = store_len % 256
            pH = store_len // 256
        # Regra dos bits: para ESC/POS usar 256 (padrão), mas pode usar 255 se necessário para compatibilidade
        cmds = b''
        # [1] Set QR code model
        cmds += b'\x1D\x28\x6B\x04\x00\x31\x41\x32\x00'
        # [2] Set QR code size (20 = 20 dots/module, máximo para maioria das impressoras)
        cmds += b'\x1D\x28\x6B\x03\x00\x31\x43\x14'
        # [3] Set error correction level (48 = L, 49 = M, 50 = Q, 51 = H)
        cmds += b'\x1D\x28\x6B\x03\x00\x31\x45\x31'
        # [4] Store data
        cmds += b'\x1D\x28\x6B' + bytes([pL, pH]) + b'\x31\x50\x30' + data.encode('utf-8')
        # [5] Print QR code
        cmds += b'\x1D\x28\x6B\x03\x00\x31\x51\x30'
        return cmds
    def escbema_qrcode(data, modulo=14, error_level=0, modo=1, use_255=False):
        # ESCBema QRCode para Bematech MP-2500/4200
        # Comando: GS kQ <ErrorLevel> <N2> <LarguraModulo> <N4> <cTam1> <cTam2> <dados>
        GS = b'\x1D'
        kQ = b'kQ'
        N2 = 0
        N4 = modo  # 1 = alfanumérico
        tam = len(data)
        if use_255:
            cTam1 = tam % 255
            cTam2 = tam // 255
        else:
            cTam1 = tam % 256
            cTam2 = tam // 256
        # Regra dos bits: para ESCBema usar 255, para ESC/POS usar 256 (apenas para ESCBema)
        cmd = (
            GS + kQ +
            bytes([error_level]) +
            bytes([N2]) +
            bytes([modulo]) +
            bytes([N4]) +
            bytes([cTam1]) +
            bytes([cTam2]) +
            data.encode('utf-8')
        )
        logging.debug(f'ESCBema CMD: {cmd}')
        return cmd
    if metodo_impressao_termica == "escpos":
        try:
            hprinter = win32print.OpenPrinter(impressora_termica)
            try:
                job = win32print.StartDocPrinter(hprinter, 1, ("Status Pedido", None, "RAW"))
                win32print.StartPagePrinter(hprinter)
                win32print.WritePrinter(hprinter, texto.encode("utf-8"))
                escpos_cmd = escpos_qrcode(url_qr)
                win32print.WritePrinter(hprinter, escpos_cmd)
                # Avanço de papel e corte automático ESC/POS
                win32print.WritePrinter(hprinter, b'\x1B\x64\x05')  # Avança 5 linhas
                win32print.WritePrinter(hprinter, b'\x1D\x56\x00')  # Corte total
                win32print.EndPagePrinter(hprinter)
                win32print.EndDocPrinter(hprinter)
            finally:
                win32print.ClosePrinter(hprinter)
        except Exception as e:
            messagebox.showerror("Erro de Impressão ESC/POS", f"Erro ao imprimir: {e}")
    elif metodo_impressao_termica == "escbema":
        try:
            hprinter = win32print.OpenPrinter(impressora_termica)
            try:
                job = win32print.StartDocPrinter(hprinter, 1, ("Status Pedido", None, "RAW"))
                win32print.StartPagePrinter(hprinter)
                win32print.WritePrinter(hprinter, texto.encode("utf-8"))
                # Tenta com 256
                try:
                    escbema_cmd = escbema_qrcode(url_qr, use_255=False)
                    logging.info(f'Enviando ESCBema QRCode (256): {escbema_cmd}')
                    win32print.WritePrinter(hprinter, escbema_cmd)
                    # Avanço de papel e corte automático ESCBema
                    win32print.WritePrinter(hprinter, b'\x1B\x64\x05')  # Avança 5 linhas
                    win32print.WritePrinter(hprinter, b'\x1D\x56\x00')  # Corte total (compatível com maioria)
                except Exception as e1:
                    logging.error(f'Erro ESCBema 256: {e1}')
                    # Tenta com 255 se falhar
                    try:
                        escbema_cmd = escbema_qrcode(url_qr, use_255=True)
                        logging.info(f'Enviando ESCBema QRCode (255): {escbema_cmd}')
                        win32print.WritePrinter(hprinter, escbema_cmd)
                        # Avanço de papel e corte automático ESCBema
                        win32print.WritePrinter(hprinter, b'\x1B\x64\x05')  # Avança 5 linhas
                        win32print.WritePrinter(hprinter, b'\x1D\x56\x00')  # Corte total
                    except Exception as e2:
                        logging.error(f'Erro ESCBema 255: {e2}')
                        win32print.WritePrinter(hprinter, qr_ascii_str.encode("utf-8"))
                win32print.EndPagePrinter(hprinter)
                win32print.EndDocPrinter(hprinter)
            finally:
                win32print.ClosePrinter(hprinter)
        except Exception as e:
            logging.error(f'Erro geral ESCBema: {e}')
            messagebox.showerror("Erro de Impressão ESC/Bema", f"Erro ao imprimir: {e}")
    elif metodo_impressao_termica == "win32print":
        try:
            hprinter = win32print.OpenPrinter(impressora_termica)
            try:
                job = win32print.StartDocPrinter(hprinter, 1, ("Status Pedido", None, "RAW"))
                win32print.StartPagePrinter(hprinter)
                win32print.WritePrinter(hprinter, texto.encode("utf-8"))
                # Tenta ESC/POS QR Code universal
                try:
                    escpos_cmd = escpos_qrcode(url_qr)
                    win32print.WritePrinter(hprinter, escpos_cmd)
                except Exception:
                    # Se falhar, tenta ESC/Bema QR Code (Bematech)
                    try:
                        escbema_cmd = escbema_qrcode(url_qr)
                        win32print.WritePrinter(hprinter, escbema_cmd)
                    except Exception:
                        # Se falhar, tenta imprimir como imagem raster
                        try:
                            from PIL import Image
                            import win32ui
                            import win32con
                            import win32gui
                            import io
                            img = Image.open(BytesIO(qr_bytes)).convert('L')
                            hdc = win32ui.CreateDC()
                            hdc.CreatePrinterDC(impressora_termica)
                            hdc.StartDoc("QR Code Pedido")
                            hdc.StartPage()
                            dib = win32ui.CreateBitmap()
                            dib.CreateCompatibleBitmap(hdc, img.width, img.height)
                            hdc.SelectObject(dib)
                            hdc.DrawState((0,0,img.width,img.height), img.tobytes(), None, win32con.DST_BITMAP)
                            hdc.EndPage()
                            hdc.EndDoc()
                            hdc.DeleteDC()
                        except Exception:
                            # Se ainda assim falhar, imprime QR em ASCII
                            win32print.WritePrinter(hprinter, qr_ascii_str.encode("utf-8"))
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
                f.write(qr_ascii_str)
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
