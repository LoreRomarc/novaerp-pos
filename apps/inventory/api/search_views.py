# apps/inventory/api/search_views.py
from django.http import JsonResponse
from django.views import View

from apps.inventory.services.search_service import InventorySearchService


class VarianteSearchAPI(View):

    def get(self, request):

        query = request.GET.get("q", "")

        variantes = InventorySearchService.search_variantes(query)

        data = InventorySearchService.serialize(variantes)

        return JsonResponse(data, safe=False)