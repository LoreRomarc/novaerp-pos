"""Tipos de movimiento legibles compartidos por Inventario y Kardex.

El código interno se conserva para auditoría, pero estas son las únicas
opciones que el usuario ve y selecciona en ambas pantallas.
"""

TIPOS_MOVIMIENTO_FILTRO = (
    ("COMPLETO", "Traslado entre sucursales"),
    ("AJUSTE_ENTRADA", "Entrada de inventario"),
    ("AJUSTE_SALIDA", "Salida por ajuste o corrección"),
    ("DANADO", "Producto dañado"),
    ("MERMA", "Merma o pérdida"),
    ("CONSUMO_INTERNO", "Uso interno"),
    ("DEVOLUCION_CLIENTE", "Devolución de cliente"),
    ("DEVOLUCION_PROVEEDOR", "Devolución a proveedor"),
    ("INICIAL", "Inventario inicial"),
)


CODIGOS_POR_TIPO = {
    # Incluye las denominaciones históricas para que un traslado antiguo y
    # uno nuevo aparezcan juntos al elegir "Traslado entre sucursales".
    "COMPLETO": {"TRASLADO", "COMPLETO", "SALIDA", "ENTRADA"},
}


def codigos_para_tipo(tipo):
    """Códigos de base de datos representados por una opción visible."""
    return CODIGOS_POR_TIPO.get(tipo, {tipo})
