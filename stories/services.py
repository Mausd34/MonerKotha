import hashlib
import hmac
import re
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models import ModerationLog, Story


def visitor_hash(request):
    """Derive a daily pseudonym without persisting the raw address."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    address = forwarded_for.split(",", 1)[0].strip() if forwarded_for else request.META.get("REMOTE_ADDR", "")
    if not address:
        return ""
    secret = settings.SECRET_KEY.encode("utf-8")
    message = f"{timezone.localdate().isoformat()}:{address}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def allow_request(request, bucket, limit, window_seconds):
    identity = visitor_hash(request)
    if not identity:
        identity = hashlib.sha256(request.session.session_key.encode()).hexdigest() if request.session.session_key else "anonymous"
    key = f"rate:{bucket}:{identity}"
    cache.add(key, 0, timeout=window_seconds)
    try:
        current = cache.incr(key)
    except ValueError:
        cache.add(key, 0, timeout=window_seconds)
        current = cache.incr(key)
    return current <= limit


def contains_contact_details(content):
    patterns = (
        r"(?i)\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b",
        r"(?i)\b(?:https?://|www\.)\S+",
        r"(?<!\w)(?:\+?88[-\s]?)?(?:01[3-9]|০১[৩-৯])(?:[-\s]?\d){8}(?!\w)",
    )
    return any(re.search(pattern, content) for pattern in patterns)


@transaction.atomic
def moderate_story(story, moderator, action, note=""):
    transitions = {
        Story.Status.PENDING: {Story.Status.APPROVED, Story.Status.REJECTED, Story.Status.REMOVED},
        Story.Status.APPROVED: {Story.Status.REMOVED},
        Story.Status.REJECTED: {Story.Status.REMOVED},
        Story.Status.REMOVED: set(),
    }
    if action not in transitions.get(story.status, set()):
        raise ValueError("This moderation transition is not allowed.")
    story.status = action
    story.moderated_at = timezone.now()
    if action == Story.Status.REMOVED:
        story.content = ""
    story.save(update_fields=("status", "moderated_at", "content"))
    log_action = {
        Story.Status.APPROVED: ModerationLog.Action.APPROVE,
        Story.Status.REJECTED: ModerationLog.Action.REJECT,
        Story.Status.REMOVED: ModerationLog.Action.REMOVE,
    }[action]
    ModerationLog.objects.create(
        story=story,
        story_public_id=story.public_id,
        moderator=moderator,
        action=log_action,
        note=note[:500],
    )
    return story
