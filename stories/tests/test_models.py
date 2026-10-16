from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from stories.models import Category, ModerationLog, Reaction, Story
from stories.services import moderate_story


class StoryModelTests(TestCase):
    def setUp(self):
        self.category, _ = Category.objects.get_or_create(slug="life", defaults={"name": "জীবন"})

    def test_new_story_has_uuid_and_is_pending(self):
        story = Story.objects.create(
            category=self.category,
            content="এই গল্পটি একটি পরীক্ষার জন্য লেখা, কোনো বাস্তব ব্যক্তির নয়।",
            consent_given=True,
            status=Story.Status.APPROVED,
        )
        self.assertEqual(story.status, Story.Status.PENDING)
        self.assertIsNotNone(story.public_id)

    def test_moderation_records_decision(self):
        story = Story.objects.create(category=self.category, content="একটি কাল্পনিক গল্পের নমুনা।", consent_given=True)
        moderator = get_user_model().objects.create_user(username="reviewer", password="test-password")
        moderate_story(story, moderator, Story.Status.APPROVED, "নির্দেশিকা মেনে চলে")
        story.refresh_from_db()
        self.assertEqual(story.status, Story.Status.APPROVED)
        self.assertEqual(story.moderation_logs.get().action, ModerationLog.Action.APPROVE)

    def test_removing_story_scrubs_its_content(self):
        story = Story.objects.create(category=self.category, content="একটি ক্ষতিকর কনটেন্টের কাল্পনিক নমুনা।", consent_given=True)
        moderator = get_user_model().objects.create_user(username="safety-reviewer", password="test-password")
        moderate_story(story, moderator, Story.Status.REMOVED)
        story.refresh_from_db()
        self.assertEqual(story.content, "")
        self.assertEqual(story.moderation_logs.get().story_public_id, story.public_id)

    def test_reaction_is_unique_per_visitor_story_and_kind(self):
        story = Story.objects.create(category=self.category, content="একটি কাল্পনিক গল্পের নমুনা।", consent_given=True)
        Reaction.objects.create(story=story, kind=Reaction.Kind.HEART, visitor_hash="a" * 64)
        with self.assertRaises(IntegrityError):
            Reaction.objects.create(story=story, kind=Reaction.Kind.HEART, visitor_hash="a" * 64)
