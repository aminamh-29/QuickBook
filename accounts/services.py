"""Account business logic: registration and token handling."""
from rest_framework.authtoken.models import Token

from referrals import services as referral_services


def register_user(*, username, email, password, phone="", referral_code=""):
    """Create a user, place them in the referral tree, and issue a token.

    Raises ``ServiceError`` for an invalid referral code.
    """
    referrer = None
    if referral_code:
        referrer = referral_services.get_referrer_by_code(referral_code)
    user = referral_services.create_user_in_tree(
        referrer=referrer,
        username=username,
        email=email,
        password=password,
        phone=phone,
    )
    token, _ = Token.objects.get_or_create(user=user)
    return user, token


def issue_token(user):
    token, _ = Token.objects.get_or_create(user=user)
    return token


def revoke_token(user):
    Token.objects.filter(user=user).delete()
