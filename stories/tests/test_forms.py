from django.test import TestCase

from stories.forms import StorySubmissionForm
from stories.models import Category, Story


class StorySubmissionFormTests(TestCase):
    def setUp(self):
        self.category, _ = Category.objects.get_or_create(slug="life", defaults={"name": "জীবন"})
        self.data = {
            "category": self.category.pk,
            "content": "এটি আমার অনুভূতির একটি কাল্পনিক লেখা, কোনো ব্যক্তিকে চেনায় না।",
            "consent_given": "on",
        }

    def test_valid_submission_is_created_pending(self):
        form = StorySubmissionForm(data=self.data)
        self.assertTrue(form.is_valid(), form.errors)
        story = form.save()
        self.assertEqual(story.status, Story.Status.PENDING)
        self.assertTrue(story.consent_given)

    def test_consent_is_mandatory(self):
        form = StorySubmissionForm(data={key: value for key, value in self.data.items() if key != "consent_given"})
        self.assertFalse(form.is_valid())
        self.assertIn("consent_given", form.errors)

    def test_contact_information_is_rejected(self):
        form = StorySubmissionForm(data={**self.data, "content": "আমাকে mail me at example@example.com"})
        self.assertFalse(form.is_valid())
        self.assertIn("content", form.errors)
        form = StorySubmissionForm(data={**self.data, "content": "আমার ফোন ০১৭১২৩৪৫৬৭৮"})
        self.assertFalse(form.is_valid())

    def test_inactive_categories_are_unavailable(self):
        self.category.is_active = False
        self.category.save()
        form = StorySubmissionForm(data=self.data)
        self.assertFalse(form.is_valid())
