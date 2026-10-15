"""Catálogo maestro editable para altas masivas de productos y variantes.

UBICACIÓN
---------
Edite exclusivamente este archivo y luego ejecute, desde la raíz del proyecto:

    python manage.py cargar_catalogo_productos

COMPORTAMIENTO SEGURO
---------------------
* Sin opciones, el comando sólo CREA productos y variantes que no existan.
* No borra, desactiva ni cambia precios de registros existentes.
* Para actualizar campos comerciales existentes use deliberadamente:

      python manage.py cargar_catalogo_productos --actualizar

* Una variante se identifica por producto + tela + color + talla. Si ya existe,
  no se duplica; conserva SKU, código de barras, stock, ventas y movimientos.
* Para prever el resultado sin escribir en la base use ``--simular``.

IMPORTANTE SOBRE CAMBIOS
------------------------
No cambie tela, color o talla de una variante existente: agregue una nueva
variante y desactive la anterior desde el ERP cuando deje de venderse. Así el
historial conserva su referencia. Si cambia el nombre de un producto, agregue
``"nombre_anterior"`` y ejecute con ``--actualizar``. Las ventas cerradas ya
guardan una copia histórica del producto, SKU, tela, color, talla y precio.

El SKU y el código de barras se generan automáticamente por el modelo. Nunca
incluya ``sku`` o ``codigo_barras`` aquí salvo que se implemente una importación
especial revisada: no conviene reescribir identificadores existentes.
"""

# Estas son las tallas que se manejan inicialmente para CADA prenda. Si una
# prenda futura necesita otro rango, cree una constante propia en lugar de
# modificar esta lista y afectar accidentalmente el catálogo completo.
TALLAS_BASE = ("Adulto", "Niño", "16", "2XL", "3XL", "4XL")


def variantes_para_telas(*telas):
    """Genera una variante por cada combinación tela/talla.

    Todas inician con color ``Sin Definir`` porque el inventario actual está en
    transición. Cuando se manejen colores reales, agregue sólo las variantes
    nuevas con el color correspondiente; no cambie las existentes.
    """
    return [
        {
            "tela": tela,
            "color": "Sin Definir",
            "talla": talla,
            # Los precios y costos reales se definen después por las listas de
            # precio y el proceso de compras/producción; nunca se inventan.
            "precio_venta": 0,
            "costo_unitario": 0,
            "stock_minimo": 0,
            "activo": True,
        }
        for tela in telas
        for talla in TALLAS_BASE
    ]


# CATÁLOGO INICIAL DE NOVAERP
# ---------------------------
# Se carga automáticamente durante el primer /setup/ y también se puede correr
# después con ``python manage.py cargar_catalogo_productos``. Es acumulativo:
# crear variantes nuevas aquí no duplica las existentes ni modifica el historial.
PRODUCTOS = [
    {
        "nombre": "Suéter",
        "descripcion": "Suéter básico",
        "activo": True,
        "variantes": variantes_para_telas(
            "Lycra Algodón",
            "Tela Fría",
            "Algodón Puro",
            "Algodón Pesado 250gr",
        ),
    },
    {
        "nombre": "Suéter Oversize",
        "descripcion": "Suéter oversize",
        "activo": True,
        "variantes": variantes_para_telas(
            "Algodón Pesado 250gr",
            "Tela Burda",
        ),
    },
    {
        "nombre": "Suéter Combinado",
        "descripcion": "Suéter combinado en lycra algodón",
        "activo": True,
        "variantes": variantes_para_telas("Lycra Algodón"),
    },
    {
        "nombre": "Short",
        "descripcion": "Short",
        "activo": True,
        "variantes": variantes_para_telas("Tela Burda", "Algodón Perchado"),
    },
    {
        "nombre": "Pantaloneta",
        "descripcion": "Pantaloneta",
        "activo": True,
        "variantes": variantes_para_telas("Tela Burda", "Algodón Perchado"),
    },
    {
        "nombre": "Pantalón con Vena",
        "descripcion": "Pantalón con vena en tela burda",
        "activo": True,
        "variantes": variantes_para_telas("Tela Burda"),
    },
    {
        "nombre": "Pantalón 3 Rayas",
        "descripcion": "Pantalón de tres rayas en tela burda",
        "activo": True,
        "variantes": variantes_para_telas("Tela Burda"),
    },
    {
        "nombre": "Jogger",
        "descripcion": "Jogger",
        "activo": True,
        "variantes": variantes_para_telas("Algodón Perchado", "Tela Burda"),
    },
    {
        "nombre": "Camiseta Polo",
        "descripcion": "Camiseta tipo polo",
        "activo": True,
        "variantes": variantes_para_telas("Tela Piqué", "Lycra Algodón"),
    },
    {
        "nombre": "Licra Larga",
        "descripcion": "Licra deportiva larga",
        "activo": True,
        "variantes": variantes_para_telas("Suplex Poliamida"),
    },
    {
        "nombre": "Licra Corta",
        "descripcion": "Licra deportiva corta",
        "activo": True,
        "variantes": variantes_para_telas("Suplex Poliamida"),
    },
    {
        "nombre": "Suéter de Pechera",
        "descripcion": "Suéter de pechera en lycra algodón",
        "activo": True,
        "variantes": variantes_para_telas("Lycra Algodón"),
    },
]

# Para agregar otra prenda, copie uno de los bloques anteriores y ajuste sólo
# nombre, descripción y telas. Para un renombre controlado agregue
# ``"nombre_anterior": "Nombre anterior"`` y use el comando con --actualizar.
