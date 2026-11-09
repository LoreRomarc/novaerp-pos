"""Generación de etiquetas de producto en cinta continua."""

from io import BytesIO

from reportlab.graphics.barcode.code128 import Code128
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _lineas(pdf, texto, ancho, fuente, tamano):
    resultado, linea = [], ""
    for palabra in str(texto).split():
        candidata = f"{linea} {palabra}".strip()
        if not linea or pdf.stringWidth(candidata, fuente, tamano) <= ancho:
            linea = candidata
        else:
            resultado.append(linea)
            linea = palabra
    if linea:
        resultado.append(linea)
    return resultado


def _nombre(variante):
    # Los separadores del catálogo son útiles en pantalla, pero en una cinta
    # estrecha hacen que la segunda línea empiece con un punto. Para impresión
    # se conservan todos los datos separados por espacios.
    return variante.nombre_completo.upper().replace(" · ", " ")


def generar_pdf_etiquetas(items, configuracion):
    """Crea una página por etiqueta con nombre, código y barras Code 128."""
    ancho = float(configuracion.ancho_mm) * mm
    alto = float(configuracion.alto_mm) * mm
    margen = float(configuracion.margen_lateral_mm) * mm
    ancho_util = ancho - (margen * 2)
    alto_barra = float(configuracion.alto_barra_mm) * mm
    salida = BytesIO()
    pdf = canvas.Canvas(salida, pagesize=(ancho, alto))

    for variante, copias in items:
        codigo = str(variante.codigo_barras or "").strip().upper()
        if not codigo:
            continue
        for _ in range(max(1, int(copias))):
            fuente, tamano = "Helvetica-Bold", float(configuracion.tamano_nombre_pt)
            lineas = _lineas(pdf, _nombre(variante), ancho_util, fuente, tamano)
            while len(lineas) > 2 and tamano > 5.5:
                tamano -= 0.5
                lineas = _lineas(pdf, _nombre(variante), ancho_util, fuente, tamano)
            if len(lineas) > 2:
                palabras = _nombre(variante).split()
                corte = max(1, len(palabras) // 2)
                lineas = [" ".join(palabras[:corte]), " ".join(palabras[corte:])]
                tamano = 5.5

            pdf.setFont(fuente, tamano)
            y = alto - (float(configuracion.margen_superior_mm) * mm) - tamano
            for linea in lineas:
                pdf.drawCentredString(ancho / 2, y, linea)
                y -= tamano + 1.5

            # El valor se escribe una sola vez fuera de las barras.
            barra = Code128(
                codigo,
                barWidth=float(configuracion.ancho_modulo_mm) * mm,
                barHeight=alto_barra,
                humanReadable=False,
            )
            if barra.width > ancho_util:
                barra = Code128(
                    codigo,
                    barWidth=(ancho_util / barra.width) * float(configuracion.ancho_modulo_mm) * mm,
                    barHeight=alto_barra,
                    humanReadable=False,
                )
            y_barra = max(
                float(configuracion.margen_inferior_mm) * mm + (float(configuracion.tamano_codigo_pt) + 4),
                y - float(configuracion.espacio_nombre_codigo_mm) * mm - alto_barra,
            )
            barra.drawOn(pdf, (ancho - barra.width) / 2, y_barra)
            pdf.setFont("Helvetica", float(configuracion.tamano_codigo_pt))
            pdf.drawCentredString(
                ancho / 2,
                y_barra - float(configuracion.espacio_codigo_texto_mm) * mm,
                codigo,
            )
            pdf.showPage()
    pdf.save()
    return salida.getvalue()
