from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import UserSerializer
from config.exceptions import ServiceError

from . import services

DEFAULT_TREE_DEPTH = 3

StatsSerializer = inline_serializer(
    "ReferralStats",
    {
        "user_id": serializers.IntegerField(),
        "left_count": serializers.IntegerField(),
        "right_count": serializers.IntegerField(),
        "total_team": serializers.IntegerField(),
    },
)


class TreeView(APIView):
    """Nested binary tree below a user. Use ``?depth=N`` (default 3, max 10)."""

    @extend_schema(
        parameters=[OpenApiParameter("depth", int, description="Levels to include (default 3, max 10)")],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request, user_id):
        user = services.get_user_or_404(user_id)
        try:
            depth = int(request.query_params.get("depth", DEFAULT_TREE_DEPTH))
        except ValueError:
            raise ServiceError("depth must be an integer.", code="invalid_depth")
        if depth < 0:
            raise ServiceError("depth must be 0 or greater.", code="invalid_depth")
        return Response(services.build_tree(user, depth))


class RootView(APIView):
    """Root user of the tree that contains the given user."""

    @extend_schema(responses={200: UserSerializer})
    def get(self, request, user_id):
        user = services.get_user_or_404(user_id)
        return Response(UserSerializer(services.get_root(user)).data)


class StatsView(APIView):
    """Left / right team counts for a user."""

    @extend_schema(responses={200: StatsSerializer})
    def get(self, request, user_id):
        user = services.get_user_or_404(user_id)
        return Response(services.get_stats(user))
