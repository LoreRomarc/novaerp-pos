from django.db.models import Q
from django.contrib.auth.models import User


class UserSearchService:

    @staticmethod
    def search(query, limit=10):

        if not query:
            return User.objects.none()

        return (
            User.objects
            .select_related("profile", "profile__sucursal")
            .filter(
                Q(username__icontains=query) |
                Q(email__icontains=query)
            )[:limit]
        )

    @staticmethod
    def serialize(users):

        return [
            {
                "id": u.id,
                "text": f"{u.username} - {u.profile.role}",
                "username": u.username,
                "email": u.email,
                "role": u.profile.role,
                "sucursal": str(u.profile.sucursal) if u.profile.sucursal else ""
            }
            for u in users
        ]