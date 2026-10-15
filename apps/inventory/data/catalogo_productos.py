"""Catálogo editable para altas masivas de productos y variantes.

Edite PRODUCTOS antes de ejecutar:
    python manage.py cargar_catalogo_productos

Cada variante reutiliza, por nombre, la tela, color y talla existentes. Si la
variante ya existe no se duplica. El SKU y el código de barras se generan de
forma automática y segura por el modelo.
"""

PRODUCTOS = [
    # Ejemplo (quite el comentario y ajuste los valores):
    # {
    #     "nombre": "Suéter",
    #     "descripcion": "",
    #     "variantes": [
    #         {
    #             "tela": "Lycra Algodón",
    #             "color": "Sin Definir",
    #             "talla": "Adulto",
    #             "precio_venta": 0,
    #             "costo_unitario": 0,
    #             "stock_minimo": 0,
    #         },
    #     ],
    # },
]
