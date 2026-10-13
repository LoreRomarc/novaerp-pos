# apps/inventory/api/search_views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from apps.inventory.mixins import InventoryAccessMixin
from apps.inventory.services.search_service import InventorySearchService


class VarianteSearchAPI(LoginRequiredMixin, InventoryAccessMixin, View):
    """Búsqueda autenticada de variantes para controles internos del inventario."""

    def get(self, request):

        query = request.GET.get("q", "")

        variantes = InventorySearchService.search_variantes(query)

        data = InventorySearchService.serialize(variantes)

        return JsonResponse(data, safe=False)
