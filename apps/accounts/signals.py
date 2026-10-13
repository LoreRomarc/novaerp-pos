# apps/accounts/signals.py
"""Señales de cuentas.

La creación del ``UserProfile`` vive en ``apps.accounts.models``. Mantener una
segunda señal aquí intentaba crear el mismo perfil dos veces y ocasionaba el
``IntegrityError`` al registrar usuarios desde Administración.
"""
