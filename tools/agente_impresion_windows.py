"""Agente local de impresión NovaERP para Windows.

Ejecutar en el computador que tiene conectada la impresora:
    py tools\agente_impresion_windows.py

El agente escucha únicamente en 127.0.0.1:8765. Recibe ZPL desde la sesión
autenticada del navegador y lo envía a la impresora seleccionada en NovaERP.
No abre puertos de red ni acepta orígenes ajenos a NovaERP.
"""

from __future__ import annotations

import ctypes
import json
import os
from ctypes import byref, c_void_p, create_string_buffer
from ctypes.wintypes import DWORD, LPCWSTR
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = "127.0.0.1"
PORT = int(os.environ.get("NOVAERP_PRINT_AGENT_PORT", "8765"))
ORIGENES = {
    item.strip().rstrip("/")
    for item in os.environ.get(
        "NOVAERP_PRINT_AGENT_ORIGINS",
        "https://novaerp-pruebas.onrender.com,http://127.0.0.1:8001,http://localhost:8001",
    ).split(",")
    if item.strip()
}


def validar_windows():
    if os.name != "nt":
        raise RuntimeError("El agente solo se puede ejecutar en Windows.")


def listar_impresoras():
    """Lee las impresoras locales/activas mediante la API de Windows."""
    validar_windows()
    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    flags = 0x00000002 | 0x00000004  # LOCAL y CONNECTIONS
    necesarias = DWORD(0)
    devueltas = DWORD(0)
    winspool.EnumPrintersW(flags, None, 4, None, 0, byref(necesarias), byref(devueltas))
    if not necesarias.value:
        return []
    buffer = ctypes.create_string_buffer(necesarias.value)
    if not winspool.EnumPrintersW(
        flags, None, 4, buffer, necesarias.value, byref(necesarias), byref(devueltas)
    ):
        raise OSError(ctypes.get_last_error(), "No se pudieron consultar las impresoras de Windows.")

    class PRINTER_INFO_4W(ctypes.Structure):
        _fields_ = [("pPrinterName", LPCWSTR), ("pServerName", LPCWSTR), ("Attributes", DWORD)]

    registros = ctypes.cast(buffer, ctypes.POINTER(PRINTER_INFO_4W))
    return sorted({registros[indice].pPrinterName for indice in range(devueltas.value) if registros[indice].pPrinterName})


def enviar_zpl(impresora: str, zpl: str):
    validar_windows()
    if not impresora or not impresora.strip():
        raise ValueError("Seleccione una impresora antes de activar la impresión automática.")
    if impresora not in listar_impresoras():
        raise ValueError(f"La impresora '{impresora}' no está disponible en este PC.")
    if not zpl.startswith("^XA") or not zpl.rstrip().endswith("^XZ"):
        raise ValueError("El trabajo de impresión no contiene ZPL válido.")

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [
            ("pDocName", LPCWSTR),
            ("pOutputFile", LPCWSTR),
            ("pDatatype", LPCWSTR),
        ]

    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    handle = c_void_p()
    if not winspool.OpenPrinterW(impresora, byref(handle), None):
        raise OSError(ctypes.get_last_error(), f"No se pudo abrir '{impresora}'.")
    try:
        documento = DOC_INFO_1("NovaERP - comprobante", None, "RAW")
        if not winspool.StartDocPrinterW(handle, 1, byref(documento)):
            raise OSError(ctypes.get_last_error(), "Windows no pudo iniciar el trabajo de impresión.")
        try:
            if not winspool.StartPagePrinter(handle):
                raise OSError(ctypes.get_last_error(), "Windows no pudo iniciar la página.")
            try:
                datos = zpl.encode("ascii", errors="replace")
                escritos = DWORD(0)
                buffer = create_string_buffer(datos)
                if not winspool.WritePrinter(handle, buffer, len(datos), byref(escritos)):
                    raise OSError(ctypes.get_last_error(), "Windows no pudo enviar el ticket.")
                if escritos.value != len(datos):
                    raise OSError("Windows recibió un ticket incompleto.")
            finally:
                winspool.EndPagePrinter(handle)
        finally:
            winspool.EndDocPrinter(handle)
    finally:
        winspool.ClosePrinter(handle)


class AgenteHandler(BaseHTTPRequestHandler):
    server_version = "NovaERPPrintAgent/1.0"

    def _origen_valido(self):
        return (self.headers.get("Origin") or "").rstrip("/") in ORIGENES

    def _respuesta(self, status, contenido):
        datos = json.dumps(contenido, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        origen = (self.headers.get("Origin") or "").rstrip("/")
        if origen in ORIGENES:
            self.send_header("Access-Control-Allow-Origin", origen)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(datos)

    def do_OPTIONS(self):
        if not self._origen_valido():
            self._respuesta(403, {"ok": False, "error": "Origen no autorizado."})
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self):
        if not self._origen_valido():
            self._respuesta(403, {"ok": False, "error": "Origen no autorizado."})
            return
        try:
            if self.path == "/status":
                self._respuesta(200, {"ok": True, "nombre": "Agente de impresión NovaERP"})
            elif self.path == "/printers":
                self._respuesta(200, {"ok": True, "printers": listar_impresoras()})
            else:
                self._respuesta(404, {"ok": False, "error": "Ruta no encontrada."})
        except Exception as error:
            self._respuesta(500, {"ok": False, "error": str(error)})

    def do_POST(self):
        if not self._origen_valido() or self.path != "/print":
            self._respuesta(403, {"ok": False, "error": "Solicitud no autorizada."})
            return
        try:
            longitud = int(self.headers.get("Content-Length", "0"))
            datos = json.loads(self.rfile.read(longitud).decode("utf-8"))
            enviar_zpl(str(datos.get("impresora", "")), str(datos.get("zpl", "")))
            self._respuesta(200, {"ok": True, "impresora": datos["impresora"]})
        except Exception as error:
            self._respuesta(400, {"ok": False, "error": str(error)})

    def log_message(self, formato, *args):
        print("[NovaERP Print Agent] " + formato % args)


if __name__ == "__main__":
    validar_windows()
    print(f"Agente NovaERP activo en http://{HOST}:{PORT}")
    print("Orígenes permitidos: " + ", ".join(sorted(ORIGENES)))
    print("No cierre esta ventana mientras use impresión automática.")
    ThreadingHTTPServer((HOST, PORT), AgenteHandler).serve_forever()
