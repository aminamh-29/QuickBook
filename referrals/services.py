"""Binary referral tree logic: placement, tree, root and team statistics."""
from collections import deque

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from config.exceptions import ConflictError, NotFoundError, ServiceError

User = get_user_model()

LEFT, RIGHT = User.Position.LEFT, User.Position.RIGHT
MAX_PLACEMENT_ATTEMPTS = 5
MAX_TREE_DEPTH = 10


def get_user_or_404(user_id):
    try:
        return User.objects.get(pk=user_id)
    except (User.DoesNotExist, ValueError, TypeError):
        raise NotFoundError("User not found.", code="user_not_found")


def get_referrer_by_code(code):
    """Return the user owning ``code`` or raise a validation error."""
    try:
        return User.objects.get(referral_code=code.strip().upper())
    except User.DoesNotExist:
        raise ServiceError("Invalid referral code.", code="invalid_referral_code")


def find_open_slot(referrer):
    """Return ``(parent, position)`` of the first free slot under ``referrer``.

    Breadth-first, level by level, checking left before right at each node.
    """
    queue = deque([referrer])
    while queue:
        node = queue.popleft()
        children = {c.position: c for c in User.objects.filter(parent=node)}
        if LEFT not in children:
            return node, LEFT
        if RIGHT not in children:
            return node, RIGHT
        queue.append(children[LEFT])
        queue.append(children[RIGHT])
    raise ServiceError("No free slot found.")  # unreachable: trees are finite


def create_user_in_tree(referrer=None, **user_fields):
    """Create a user and place them in the referral tree.

    Without a referrer the user becomes the root of a new tree. Concurrent
    registrations may pick the same slot; the ``(parent, position)`` unique
    constraint rejects the loser, which then retries with a fresh search.
    """
    password = user_fields.pop("password")
    for _ in range(MAX_PLACEMENT_ATTEMPTS):
        try:
            with transaction.atomic():
                parent = position = None
                if referrer is not None:
                    parent, position = find_open_slot(referrer)
                user = User(
                    referrer=referrer,
                    parent=parent,
                    position=position,
                    **user_fields,
                )
                user.set_password(password)
                user.save()
                return user
        except IntegrityError:
            # Slot taken by a concurrent request (or duplicate username/email,
            # which we surface as-is on the final attempt).
            if User.objects.filter(
                username=user_fields.get("username")
            ).exists() or User.objects.filter(email=user_fields.get("email")).exists():
                raise
            continue
    raise ConflictError("Could not place user in the network, please retry.")


def get_root(user):
    """Walk up the parent chain and return the root of ``user``'s tree."""
    node = user
    seen = set()
    while node.parent_id is not None and node.pk not in seen:
        seen.add(node.pk)
        node = node.parent
    return node


def _node(user):
    return {
        "id": user.pk,
        "username": user.username,
        "referral_code": user.referral_code,
        "position": user.position,
        "left": None,
        "right": None,
    }


def build_tree(user, depth=3):
    """Return ``user``'s subtree as nested dicts, ``depth`` levels below them.

    One query per level rather than one per node.
    """
    depth = max(0, min(depth, MAX_TREE_DEPTH))
    root = _node(user)
    level = {user.pk: root}
    for _ in range(depth):
        if not level:
            break
        children = User.objects.filter(parent_id__in=level.keys())
        next_level = {}
        for child in children:
            node = _node(child)
            level[child.parent_id][child.position] = node
            next_level[child.pk] = node
        level = next_level
    return root


def _subtree_size(user_id):
    """Number of users in the subtree rooted at ``user_id`` (inclusive)."""
    if user_id is None:
        return 0
    total, frontier = 0, [user_id]
    while frontier:
        total += len(frontier)
        frontier = list(
            User.objects.filter(parent_id__in=frontier).values_list("pk", flat=True)
        )
    return total


def get_stats(user):
    """Left/right team counts (all descendants on each side)."""
    children = {c.position: c.pk for c in User.objects.filter(parent=user)}
    left = _subtree_size(children.get(LEFT))
    right = _subtree_size(children.get(RIGHT))
    return {
        "user_id": user.pk,
        "left_count": left,
        "right_count": right,
        "total_team": left + right,
    }


def get_descendants(user, max_depth=MAX_TREE_DEPTH):
    """Return ``[(descendant, depth), ...]`` for everyone below ``user``.

    ``depth`` is 1 for direct children. Used for searching within a tree.
    """
    found, frontier = [], [user.pk]
    for depth in range(1, max_depth + 1):
        if not frontier:
            break
        level = list(User.objects.filter(parent_id__in=frontier).order_by("pk"))
        found.extend((u, depth) for u in level)
        frontier = [u.pk for u in level]
    return found
