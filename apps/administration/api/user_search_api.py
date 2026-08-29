from django.http import JsonResponse
from django.views import View

from apps.administration.services.user_search_service import UserSearchService
from apps.administration.mixins import SuperAdminRequiredMixin


class UserSearchAPI(SuperAdminRequiredMixin, View):

    def get(self, request):
        query = request.GET.get("q", "")

        users = UserSearchService.search(query)
        data = UserSearchService.serialize(users)

        return JsonResponse(data, safe=False)
