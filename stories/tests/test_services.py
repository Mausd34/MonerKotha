from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from stories.models import Category, ModerationLog, Story
from stories.services import allow_request, contains_contact_details, moderate_story


class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.request = RequestFactory().get("/")
        self.request.META["REMOTE_ADDR"] = "203.0.113.20"

    def test_bucket_enforces_limit(self):
        self.assertTrue(allow_request(self.request, "unit-test", 2, 60))
        self.assertTrue(allow_request(self.request, "unit-test", 2, 60))
        self.assertFalse(allow_request(self.request, "unit-test", 2, 60))

    def test_contact_data_patterns_cover_bangladesh_digits(self):
        self.assertTrue(contains_contact_details("আমার নম্বর ০১৭১২৩৪৫৬৭৮"))
        self.assertTrue(contains_contact_details("mail me: test@example.com"))
        self.assertTrue(contains_contact_details("visit https://example.com"))
        self.assertFalse(contains_contact_details("আজ মনটা অনেক হালকা লাগছে।"))


class OperationalCommandTests(TestCase):
    def test_demo_seed_is_idempotent_and_keeps_every_story_pending(self):
        call_command("seed_demo", stdout=StringIO())
        call_command("seed_demo", stdout=StringIO())
        self.assertEqual(Story.objects.filter(is_demo=True).count(), 6)
        self.assertEqual(Story.objects.filter(is_demo=True).exclude(status=Story.Status.PENDING).count(), 0)

    def test_demo_seed_with_approve_flag_approves_stories(self):
        call_command("seed_demo", "--approve", stdout=StringIO())
        self.assertEqual(Story.objects.filter(is_demo=True, status=Story.Status.APPROVED).count(), 6)

    def test_retention_command_requires_execute_and_preserves_audit_id(self):
        category = Category.objects.get(slug="life")
        old_time = timezone.now() - timedelta(days=31)
        story = Story.objects.create(
            category=category,
            content="এটি মুছে ফেলার নীতির একটি কাল্পনিক নমুনা গল্প।",
            consent_given=True,
        )
        moderator = get_user_model().objects.create_user(username="retention-reviewer", password="test-password")
        moderate_story(story, moderator, Story.Status.REJECTED)
        Story.objects.filter(pk=story.pk).update(moderated_at=old_time)
        audit = ModerationLog.objects.get(story=story)
        with self.assertRaises(CommandError):
            call_command("purge_retained_data", stdout=StringIO())
        call_command("purge_retained_data", "--execute", stdout=StringIO())
        self.assertFalse(Story.objects.filter(pk=story.pk).exists())
        audit.refresh_from_db()
        self.assertIsNone(audit.story)
        self.assertEqual(audit.story_public_id, story.public_id)
