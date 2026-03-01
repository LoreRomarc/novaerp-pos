# NOVAERP

Sistema profesional de facturación, inventario y producción textil
desarrollado en Django.

---

## Descripción

Novaerp es un sistema diseñado para múltiples sucursales.
Permite:

- Control de inventario por talla y color
- Sistema POS
- Control de caja
- Producción textil
- Pagos con datáfono

---

## Tecnologías utilizadas

- Python 3
- Django
- JavaScript
- PostgreSQL (producción)
- PostgreSQL (desarrollo)

---

## Instalación en entorno local

1. Crear entorno virtual:
   python -m venv venv

2. Activar entorno:
   source venv/Scripts/activate  (Windows Git Bash)

3. Instalar dependencias:
   pip install -r requirements.txt

4. Aplicar migraciones:
   python manage.py migrate

5. Ejecutar servidor:
   python manage.py runserver