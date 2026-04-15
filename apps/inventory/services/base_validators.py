# apps/inventory/services/base_validators.py

from django.core.exceptions import ValidationError


class BaseInventoryValidator:

    @staticmethod
    def validar_usuario_y_sucursal(user):
        if not user or not user.is_authenticated:
            raise ValidationError("Usuario no autenticado.")

        profile = getattr(user, "profile", None)

        if not profile:
            raise ValidationError("Usuario sin perfil.")

        if not profile.sucursal:
            raise ValidationError("Usuario sin sucursal asignada.")

        return profile.sucursal


    @staticmethod
    def validar_sucursal(sucursal):
        if not sucursal:
            raise ValidationError("Sucursal requerida.")

        return sucursal


    @staticmethod
    def validar_cantidad(cantidad, contexto="movimiento"):

        try:
            cantidad = float(cantidad)
        except (TypeError, ValueError):
            raise ValidationError(f"Cantidad inválida en {contexto}.")

        if cantidad <= 0:
            raise ValidationError(f"Cantidad debe ser mayor a 0 en {contexto}.")

        return cantidad


    @staticmethod
    def validar_stock_disponible(stock, cantidad, contexto="movimiento"):

        if not stock:
            raise ValidationError(f"No existe stock en {contexto}.")

        if stock.cantidad < cantidad:
            raise ValidationError(f"Stock insuficiente en {contexto}.")