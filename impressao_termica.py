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
    # Gera a URL do QR Code
    url_qr = f"https://autopyweb.com.br/grafica/atualizacao.html?numero={pedido['numero']}&status={pedido['status']}"
    # Gera o QR Code como imagem
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(url_qr)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")
    # Salva a imagem do QR em um buffer
    buffer = BytesIO()
    img_qr.save(buffer, format="PNG")
    qr_bytes = buffer.getvalue()
    buffer.close()
    texto = (
        f"Pedido: {pedido['numero']}\nCliente: {pedido['nome']}\nStatus: {status_descricoes.get(status_cores[pedido['status']-1],'')}\nData: {pedido['datahora']}\n"
        "\n\n\n\n"  # 4 linhas em branco ao final
        "--------------------------\n"
        f"Acompanhe: {url_qr}\n"
    )
    if metodo_impressao_termica == "win32print":
        try:
            hprinter = win32print.OpenPrinter(impressora_termica)
            try:
                job = win32print.StartDocPrinter(hprinter, 1, ("Status Pedido", None, "RAW"))
                win32print.StartPagePrinter(hprinter)
                win32print.WritePrinter(hprinter, texto.encode("utf-8"))
                # Tenta imprimir o QR Code (apenas impressoras compatíveis com imagem RAW)
                try:
                    import win32ui
                    import win32con
                    from PIL import ImageWin
                    bmp = img_qr.convert('RGB')
                    hdc = win32ui.CreateDC()
                    hdc.CreatePrinterDC(impressora_termica)
                    dib = ImageWin.Dib(bmp)
                    dib.draw(hdc.GetHandleOutput(), (0, 200, 200, 400))
                    hdc.EndDoc()
                    hdc.DeleteDC()
                except Exception:
                    pass  # Se não conseguir imprimir imagem, ignora
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
