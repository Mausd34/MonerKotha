import json

from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from stories.models import Category, DeletionRequest, Reaction, Report, Story


class PublicApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.category, _ = Category.objects.get_or_create(slug="life", defaults={"name": "জীবন"})
        Category.objects.update_or_create(
            slug="hidden",
            defaults={"name": "লুকানো", "is_active": False},
        )
        self.pending = Story.objects.create(
            category=self.category,
            content="এটি মডারেশনের অপেক্ষায় থাকা একটি কাল্পনিক গল্প।",
            consent_given=True,
        )
        self.approved = Story.objects.create(
            category=self.category,
            content="এটি প্রকাশিত একটি সম্পূর্ণ কাল্পনিক গল্পের নমুনা।",
            consent_given=True,
        )
        self.approved.status = Story.Status.APPROVED
        self.approved.save(update_fields=("status",))

    def post_json(self, url, data, client=None):
        return (client or self.client).post(url, data=json.dumps(data), content_type="application/json")

    def test_categories_only_exposes_active_categories(self):
        response = self.client.get(reverse("api-categories"))
        self.assertEqual(response.status_code, 200)
        slugs = [item["slug"] for item in response.json()["results"]]
        self.assertIn("life", slugs)
        self.assertNotIn("hidden", slugs)

    def test_story_feed_only_exposes_approved_stories_and_paginates(self):
        response = self.client.get(reverse("api-story-list"))
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["id"], str(self.approved.public_id))
        self.assertNotIn("status", payload["results"][0])

    def test_story_feed_rejects_unknown_categories_and_sort_values(self):
        category_response = self.client.get(reverse("api-story-list"), {"category": "missing"})
        sort_response = self.client.get(reverse("api-story-list"), {"sort": "random"})
        self.assertEqual(category_response.status_code, 400)
        self.assertEqual(category_response.json()["error"]["code"], "invalid_category")
        self.assertEqual(sort_response.status_code, 400)
        self.assertEqual(sort_response.json()["error"]["code"], "invalid_sort")

    def test_story_detail_hides_unapproved_stories(self):
        response = self.client.get(reverse("api-story-detail", args=[self.pending.public_id]))
        self.assertEqual(response.status_code, 404)

    def test_story_creation_uses_form_validation_and_starts_pending(self):
        response = self.post_json(
            reverse("api-story-create"),
            {
                "category": self.category.pk,
                "content": "এটি API দিয়ে জমা দেওয়া নতুন কাল্পনিক গল্প।",
                "consent_given": True,
            },
        )
        self.assertEqual(response.status_code, 201)
        created = Story.objects.get(public_id=response.json()["result"]["id"])
        self.assertEqual(created.status, Story.Status.PENDING)

    def test_story_creation_rejects_contact_details(self):
        response = self.post_json(
            reverse("api-story-create"),
            {"category": self.category.pk, "content": "আমার ইমেইল hello@example.com", "consent_given": True},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
        self.assertFalse(Story.objects.filter(content__contains="hello@example.com").exists())

    def test_story_creation_requires_json(self):
        response = self.client.post(reverse("api-story-create"), {"content": "form data"})
        self.assertEqual(response.status_code, 415)

    def test_reaction_is_idempotent_for_each_visitor_and_kind(self):
        url = reverse("api-story-react", args=[self.approved.public_id])
        first = self.post_json(url, {"kind": Reaction.Kind.HEART})
        duplicate = self.post_json(url, {"kind": Reaction.Kind.HEART})
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["result"]["created"])
        self.assertFalse(duplicate.json()["result"]["created"])
        self.assertEqual(Reaction.objects.filter(story=self.approved).count(), 1)

    def test_report_is_validated_and_associated_with_story(self):
        response = self.post_json(
            reverse("api-story-report", args=[self.approved.public_id]),
            {"reason": Report.Reason.PERSONAL, "details": "একটি যাচাইয়ের নমুনা।"},
        )
        self.assertEqual(response.status_code, 201)
        report = Report.objects.get(story=self.approved)
        self.assertEqual(report.story_public_id, self.approved.public_id)

    def test_deletion_request_is_created_for_url_story(self):
        response = self.post_json(
            reverse("api-story-deletion-request", args=[self.approved.public_id]),
            {"reason": "অনুরোধের নমুনা"},
        )
        self.assertEqual(response.status_code, 202)
        request = DeletionRequest.objects.get(story=self.approved)
        self.assertEqual(request.story_public_id, self.approved.public_id)

    def test_write_api_keeps_csrf_protection(self):
        client = Client(enforce_csrf_checks=True)
        response = self.post_json(
            reverse("api-story-create"),
            {"category": self.category.pk, "content": "এটি CSRF পরীক্ষার কাল্পনিক গল্পের নমুনা।", "consent_given": True},
            client=client,
        )
        self.assertEqual(response.status_code, 403)
