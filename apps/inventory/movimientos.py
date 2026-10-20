"""Categorías simples compartidas por las pantallas de inventario.

Los valores internos del Kardex son deliberadamente detallados para conservar
la trazabilidad.  La interfaz, en cambio, usa estas tres categorías para que
la búsqueda sea la misma en Movimientos y Kardex.
"""

FILTROS_TIPO_MOVIMIENTO = (
    ("ENTRADA", "Entradas"),
    ("SALIDA", "Salidas"),
    ("TRASLADO", "Traslados entre sucursales"),
)


CODIGOS_POR_FILTRO = {
    # Una anulación devuelve unidades, por eso se considera una entrada.
    "ENTRADA": {
        "AJUSTE_ENTRADA",
        "DEVOLUCION_CLIENTE",
        "PRODUCCION",
        "INICIAL",
        "ANULACION",
    },
    "SALIDA": {
        "VENTA",
        "AJUSTE_SALIDA",
        "DANADO",
        "MERMA",
        "CONSUMO_INTERNO",
        "DEVOLUCION_PROVEEDOR",
    },
    # SALIDA y ENTRADA son códigos históricos de traslados, no las
    # categorías simplificadas usadas por el filtro de pantalla.
    "TRASLADO": {"TRASLADO", "COMPLETO", "SALIDA", "ENTRADA"},
}


def codigos_para_filtro(tipo_filtro):
    """Obtiene los códigos persistidos que representa una categoría UI."""
    return CODIGOS_POR_FILTRO.get(tipo_filtro, set())
