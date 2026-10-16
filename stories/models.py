import uuid

from django.conf import settings
from django.core.validators import MaxLengthValidator, MinLengthValidator
from django.db import models
from django.utils import timezone


class Category(models.Model):
    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=40)
    emoji = models.CharField(max_length=8, default="💭")
    description = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Story(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "পর্যালোচনাধীন"
        APPROVED = "approved", "প্রকাশিত"
        REJECTED = "rejected", "প্রত্যাখ্যাত"
        REMOVED = "removed", "সরানো হয়েছে"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="stories")
    content = models.TextField(validators=[MinLengthValidator(20), MaxLengthValidator(3000)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    consent_given = models.BooleanField(default=False)
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    moderated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "-created_at")),
        ]

    @property
    def reaction_count(self):
        if hasattr(self, "_reaction_count"):
            return self._reaction_count
        return self.reactions.count()

    def __str__(self):
        return f"{self.public_id} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.status = self.Status.PENDING
            self.moderated_at = None
        super().save(*args, **kwargs)


class Reaction(models.Model):
    class Kind(models.TextChoices):
        HEART = "heart", "❤️"
        HUG = "hug", "🫂"
        LIGHT = "light", "✨"

    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="reactions")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    visitor_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("story", "kind", "visitor_hash"), name="unique_visitor_story_reaction"),
        ]


class Report(models.Model):
    class Reason(models.TextChoices):
        PERSONAL = "personal", "ব্যক্তিগত তথ্য প্রকাশ"
        HARASSMENT = "harassment", "হয়রানি বা হুমকি"
        INTIMATE = "intimate", "সম্মতি ছাড়া অন্তরঙ্গ বিষয়"
        FALSE = "false", "ক্ষতিকর বা যাচাইহীন অভিযোগ"
        OTHER = "other", "অন্যান্য"

    story = models.ForeignKey(Story, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    story_public_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    reason = models.CharField(max_length=16, choices=Reason.choices)
    details = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        if self._state.adding and self.story_id:
            self.story_public_id = self.story.public_id
        super().save(*args, **kwargs)


class DailyPrompt(models.Model):
    prompt = models.CharField(max_length=240)
    active_date = models.DateField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-active_date",)

    def __str__(self):
        return f"{self.active_date}: {self.prompt}"


class ModerationLog(models.Model):
    class Action(models.TextChoices):
        APPROVE = "approve", "অনুমোদন"
        REJECT = "reject", "প্রত্যাখ্যান"
        REMOVE = "remove", "সরানো"
        NOTE = "note", "নোট"

    story = models.ForeignKey(Story, on_delete=models.SET_NULL, null=True, blank=True, related_name="moderation_logs")
    story_public_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=10, choices=Action.choices)
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        if self._state.adding and self.story_id:
            self.story_public_id = self.story.public_id
        super().save(*args, **kwargs)


class DeletionRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "অপেক্ষমাণ"
        COMPLETED = "completed", "সম্পন্ন"
        DECLINED = "declined", "প্রত্যাখ্যাত"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    story = models.ForeignKey(Story, on_delete=models.SET_NULL, null=True, blank=True, related_name="deletion_requests")
    story_public_id = models.UUIDField(db_index=True)
    reason = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
