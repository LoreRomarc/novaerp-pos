"""Conector local de impresión para NovaERP en Windows.

Se instala una sola vez con ``instalar_conector_impresion.ps1``. Escucha
solamente en 127.0.0.1, por lo que una instalación web del ERP puede imprimir
en las impresoras que pertenecen a este computador sin QZ Tray ni certificados.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import sys
import winreg
from ctypes import POINTER, byref, c_byte, c_int, c_void_p
from ctypes.wintypes import DWORD, LPCWSTR
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = "127.0.0.1"
PORT = 8765
LOG_PATH = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NovaERP" / "print-connector.log"
DEFAULT_ORIGINS = {
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8001",
    "http://localhost:8000",
    "http://localhost:8001",
    "https://novaerp-pruebas.onrender.com",
}


def allowed_origins():
    configured = os.environ.get("NOVAERP_ALLOWED_ORIGINS", "")
    return DEFAULT_ORIGINS | {item.strip().rstrip("/") for item in configured.split(",") if item.strip()}


def is_allowed_origin(origin):
    if not origin:
        return False
    origin = origin.rstrip("/")
    return origin in allowed_origins()


def instalar_inicio_automatico():
    """Registra el ejecutable en el inicio del usuario, sin administrador.

    Solo se activa en el .exe distribuible. Al ejecutar el archivo por primera
    vez en una caja, queda instalado en HKCU y no necesita terminal, Python ni
    la carpeta de NovaERP.
    """
    if not getattr(sys, "frozen", False):
        return False
    value = f'"{sys.executable}" --silent'
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        try:
            current, _ = winreg.QueryValueEx(key, "NovaERPPrintConnector")
        except FileNotFoundError:
            current = None
        if current == value:
            return False
        winreg.SetValueEx(key, "NovaERPPrintConnector", 0, winreg.REG_SZ, value)
    return True


def default_printer():
    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    length = DWORD(0)
    winspool.GetDefaultPrinterW(None, byref(length))
    if not length.value:
        raise RuntimeError("Windows no tiene una impresora predeterminada.")
    buffer = ctypes.create_unicode_buffer(length.value)
    if not winspool.GetDefaultPrinterW(buffer, byref(length)):
        raise RuntimeError("Windows no pudo consultar la impresora predeterminada.")
    return buffer.value


def installed_printers():
    class PRINTER_INFO_4W(ctypes.Structure):
        _fields_ = [("pPrinterName", LPCWSTR), ("pServerName", LPCWSTR), ("Attributes", DWORD)]

    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    needed, returned = DWORD(0), DWORD(0)
    flags = 0x00000002 | 0x00000004  # local + conexiones de red
    winspool.EnumPrintersW(flags, None, 4, None, 0, byref(needed), byref(returned))
    if not needed.value:
        return []
    data = (c_byte * needed.value)()
    if not winspool.EnumPrintersW(flags, None, 4, data, needed.value, byref(needed), byref(returned)):
        raise RuntimeError("Windows no pudo listar las impresoras instaladas.")
    printers = ctypes.cast(data, POINTER(PRINTER_INFO_4W))
    return sorted({printers[index].pPrinterName for index in range(returned.value) if printers[index].pPrinterName}, key=str.casefold)


def raw_print(printer, content, title):
    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [("pDocName", LPCWSTR), ("pOutputFile", LPCWSTR), ("pDatatype", LPCWSTR)]

    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    handle = c_void_p()
    if not winspool.OpenPrinterW(printer, byref(handle), None):
        raise RuntimeError(f"No fue posible abrir la impresora '{printer}'.")
    try:
        document = DOC_INFO_1(title, None, "RAW")
        if not winspool.StartDocPrinterW(handle, 1, byref(document)):
            raise RuntimeError("Windows no pudo iniciar el trabajo de impresión.")
        try:
            if not winspool.StartPagePrinter(handle):
                raise RuntimeError("Windows no pudo iniciar la página de impresión.")
            try:
                written = DWORD(0)
                data = content.encode("ascii", errors="replace")
                buffer = ctypes.create_string_buffer(data)
                if not winspool.WritePrinter(handle, buffer, len(data), byref(written)):
                    raise RuntimeError("Windows no pudo enviar el ticket a la impresora.")
            finally:
                winspool.EndPagePrinter(handle)
        finally:
            winspool.EndDocPrinter(handle)
    finally:
        winspool.ClosePrinter(handle)


def windows_text_print(printer, content, title, columns=42):
    """Imprime un ticket POS, aprovechando todo el ancho del driver Windows.

    El ERP envía filas semánticas, no posiciones fijas.  El conector compone
    las columnas en el computador que tiene instalada la impresora, por lo
    que un ticket de 58 mm conserva alineación aunque cambie el controlador.
    """
    class DOCINFOW(ctypes.Structure):
        _fields_ = [("cbSize", c_int), ("lpszDocName", LPCWSTR), ("lpszOutput", LPCWSTR), ("lpszDatatype", LPCWSTR), ("fwType", DWORD)]

    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    gdi32.CreateDCW.restype = c_void_p
    gdi32.CreateFontW.restype = c_void_p
    gdi32.SelectObject.restype = c_void_p
    gdi32.StartDocW.restype = c_int
    gdi32.StartPage.restype = c_int
    gdi32.GetTextExtentPoint32W.restype = c_int
    hdc = gdi32.CreateDCW("WINSPOOL", printer, None, None)
    if not hdc:
        raise RuntimeError(f"Windows no pudo inicializar el controlador de '{printer}'.")
    font = c_void_p()
    previous = c_void_p()
    try:
        info = DOCINFOW(ctypes.sizeof(DOCINFOW), title, None, None, 0)
        if gdi32.StartDocW(hdc, byref(info)) <= 0:
            raise RuntimeError("Windows no pudo iniciar el documento de impresión.")
        try:
            if gdi32.StartPage(hdc) <= 0:
                raise RuntimeError("Windows no pudo iniciar la página de impresión.")
            try:
                width = gdi32.GetDeviceCaps(hdc, 8)  # HORZRES
                x = max(4, int(width * 0.03))
                usable = max(1, width - (x * 2))
                columns = max(24, min(80, int(columns or 42)))
                font_width = max(1, usable // columns)
                font_height = max(16, min(28, int(font_width * 1.9)))
                font = gdi32.CreateFontW(
                    -font_height,
                    font_width,
                    0,
                    0,
                    400,
                    False,
                    False,
                    False,
                    1,
                    0,
                    0,
                    4,
                    0,
                    "Courier New",
                )
                if not font:
                    raise RuntimeError("Windows no pudo crear la fuente de impresión.")
                previous = gdi32.SelectObject(hdc, font)

                class SIZE(ctypes.Structure):
                    _fields_ = [("cx", c_int), ("cy", c_int)]

                def text_width(value):
                    size = SIZE()
                    if gdi32.GetTextExtentPoint32W(hdc, value, len(value), byref(size)):
                        return size.cx
                    return len(value) * font_width

                def draw(x_pos, value, y_pos):
                    if value and not gdi32.TextOutW(hdc, x_pos, y_pos, value, len(value)):
                        raise RuntimeError("Windows no pudo dibujar el ticket.")

                y = max(6, int(width * 0.04))
                line_height = font_height + max(4, font_height // 3)
                for raw_line in content.splitlines() or [""]:
                    if "\x1f" in raw_line:
                        left, right = raw_line.split("\x1f", 1)
                        right_x = min(
                            x + usable - text_width(right),
                            x + text_width(left) + font_width,
                        )
                        draw(x, left, y)
                        draw(max(x, right_x), right, y)
                    elif "\x1e" in raw_line:
                        left, right = raw_line.split("\x1e", 1)
                        draw(x, left, y)
                        draw(x + usable - text_width(right), right, y)
                    else:
                        draw(x, raw_line, y)
                    y += line_height
            finally:
                gdi32.EndPage(hdc)
        finally:
            gdi32.EndDoc(hdc)
            if font:
                gdi32.SelectObject(hdc, previous)
    finally:
        if font:
            gdi32.DeleteObject(font)
        gdi32.DeleteDC(hdc)


class Handler(BaseHTTPRequestHandler):
    server_version = "NovaERPPrintConnector/1.0"

    def log_message(self, format, *args):
        logging.info("%s - %s", self.address_string(), format % args)

    def _json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        origin = self.headers.get("Origin")
        if is_allowed_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        origin = self.headers.get("Origin")
        if not is_allowed_origin(origin):
            self._json(403, {"detail": "Origen no autorizado."})
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True})
        elif self.path == "/printers":
            try:
                self._json(200, {"printers": installed_printers(), "default": default_printer()})
            except Exception as error:
                logging.exception("No fue posible listar impresoras")
                self._json(500, {"detail": str(error)})
        else:
            self._json(404, {"detail": "Ruta no encontrada."})

    def do_POST(self):
        if self.path != "/print":
            self._json(404, {"detail": "Ruta no encontrada."})
            return
        if not is_allowed_origin(self.headers.get("Origin")):
            self._json(403, {"detail": "Origen no autorizado."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            printer = str(payload.get("impresora") or default_printer()).strip()
            kind = payload.get("tipo")
            title = str(payload.get("titulo") or "NovaERP - comprobante")[:180]
            if kind == "raw-zpl":
                raw_print(printer, str(payload.get("datos") or ""), title)
            elif kind == "texto-windows":
                windows_text_print(
                    printer,
                    str(payload.get("contenido") or ""),
                    title,
                    columns=payload.get("columnas", 42),
                )
            else:
                raise RuntimeError("Formato de impresión no soportado.")
            self._json(200, {"ok": True, "printer": printer})
        except Exception as error:
            logging.exception("Error imprimiendo")
            self._json(500, {"detail": str(error)})


if __name__ == "__main__":
    installed_now = instalar_inicio_automatico()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("Iniciando conector en %s:%s", HOST, PORT)
    if installed_now and "--silent" not in sys.argv:
        ctypes.windll.user32.MessageBoxW(
            0,
            "El conector de impresión NovaERP quedó instalado. Se iniciará automáticamente con Windows; puede cerrar esta ventana y no necesita usar terminal.",
            "NovaERP · impresión lista",
            0x40,
        )
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
