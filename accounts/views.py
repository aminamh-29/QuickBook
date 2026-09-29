from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import services
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


AuthResponse = inline_serializer(
    "AuthResponse", {"user": UserSerializer(), "token": serializers.CharField()}
)


class RegisterView(APIView):
    """Register a user, optionally with a referral code."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"
    serializer_class = RegisterSerializer

    @extend_schema(request=RegisterSerializer, responses={201: AuthResponse})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, token = services.register_user(**serializer.validated_data)
        return Response(
            {"user": UserSerializer(user).data, "token": token.key},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"
    serializer_class = LoginSerializer

    @extend_schema(request=LoginSerializer, responses={200: AuthResponse})
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token = services.issue_token(user)
        return Response({"user": UserSerializer(user).data, "token": token.key})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        services.revoke_token(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
