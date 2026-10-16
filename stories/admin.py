from django.contrib import admin, messages
from django.utils import timezone

from .models import Category, DailyPrompt, DeletionRequest, ModerationLog, Reaction, Report, Story
from .services import moderate_story


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ("public_id", "category", "status", "created_at", "is_demo")
    list_filter = ("status", "category", "is_demo")
    search_fields = ("content", "public_id")
    readonly_fields = ("public_id", "created_at", "moderated_at", "consent_given")
    exclude = ("status", "moderated_at")
    actions = ("approve_stories", "reject_stories", "remove_stories")

    @admin.action(description="নির্বাচিত গল্প অনুমোদন")
    def approve_stories(self, request, queryset):
        self._apply_moderation(request, queryset.filter(status=Story.Status.PENDING), Story.Status.APPROVED)

    @admin.action(description="নির্বাচিত গল্প প্রত্যাখ্যান")
    def reject_stories(self, request, queryset):
        self._apply_moderation(request, queryset.filter(status=Story.Status.PENDING), Story.Status.REJECTED)

    @admin.action(description="নির্বাচিত প্রকাশিত গল্প সরান")
    def remove_stories(self, request, queryset):
        self._apply_moderation(
            request,
            queryset.filter(status__in=(Story.Status.PENDING, Story.Status.APPROVED, Story.Status.REJECTED)),
            Story.Status.REMOVED,
        )

    @staticmethod
    def _apply_moderation(request, queryset, status):
        for story in queryset:
            moderate_story(story, request.user, status)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("story_public_id", "reason", "created_at", "is_resolved")
    list_filter = ("reason", "is_resolved")
    readonly_fields = ("story", "story_public_id", "reason", "details", "created_at", "is_resolved", "resolved_at")


@admin.register(DeletionRequest)
class DeletionRequestAdmin(admin.ModelAdmin):
    list_display = ("public_id", "story_public_id", "status", "created_at")
    list_filter = ("status", "created_at")
    readonly_fields = ("public_id", "story", "story_public_id", "reason", "created_at")


admin.site.register(Category)
admin.site.register(DailyPrompt)
admin.site.register(Reaction)


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = ("story_public_id", "action", "moderator", "created_at")
    list_filter = ("action", "created_at")
    readonly_fields = ("story", "story_public_id", "moderator", "action", "note", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
