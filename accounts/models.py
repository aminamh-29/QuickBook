from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.utils.crypto import get_random_string

REFERRAL_CODE_LENGTH = 8
REFERRAL_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no look-alikes


class User(AbstractUser):
    """Platform user, also a node in the binary referral tree.

    ``referrer`` is the user whose code was used at signup. ``parent`` is the
    node the user was actually placed under (the referrer, or a descendant of
    the referrer when the referrer's direct slots were full).
    """

    class Position(models.TextChoices):
        LEFT = "left", "Left"
        RIGHT = "right", "Right"

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    referral_code = models.CharField(
        max_length=REFERRAL_CODE_LENGTH, unique=True, editable=False
    )
    referrer = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referred_users",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    position = models.CharField(
        max_length=5, choices=Position.choices, null=True, blank=True
    )

    class Meta:
        constraints = [
            # A node can have at most one left and one right child.
            models.UniqueConstraint(
                fields=["parent", "position"], name="unique_child_slot"
            ),
            # parent and position are either both set or both empty.
            models.CheckConstraint(
                condition=Q(parent__isnull=True, position__isnull=True)
                | Q(parent__isnull=False, position__isnull=False),
                name="parent_and_position_together",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        super().save(*args, **kwargs)

    @classmethod
    def generate_referral_code(cls):
        """Return a referral code not used by any existing user."""
        while True:
            code = get_random_string(REFERRAL_CODE_LENGTH, REFERRAL_CODE_ALPHABET)
            if not cls.objects.filter(referral_code=code).exists():
                return code
