from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from stories.models import Category, DeletionRequest, Report, Story
from stories.services import moderate_story


class PublicViewTests(TestCase):
    def setUp(self):
        self.category, _ = Category.objects.get_or_create(slug="life", defaults={"name": "জীবন"})
        self.pending = Story.objects.create(category=self.category, content="এটি অপেক্ষমাণ গল্পের নমুনা।", consent_given=True)
        self.approved = Story.objects.create(
            category=self.category,
            content="এটি প্রকাশিত একটি সম্পূর্ণ কাল্পনিক গল্পের নমুনা।",
            consent_given=True,
        )
        self.publisher = get_user_model().objects.create_user(username="publisher", password="test-password")
        moderate_story(self.approved, self.publisher, Story.Status.APPROVED)

    def test_home_only_displays_approved_stories(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, self.approved.content)
        self.assertNotContains(response, self.pending.content)

    def test_search_with_no_matches_has_a_no_results_state(self):
        response = self.client.get(reverse("home"), {"q": "কোনো-গল্প-নেই-এমন-শব্দ"})
        self.assertContains(response, "এই খোঁজে কোনো গল্প পাওয়া যায়নি")

    def test_feed_paginates_and_preserves_category_filter(self):
        for index in range(12):
            story = Story.objects.create(
                category=self.category,
                content=f"এটি pagination-এর জন্য কাল্পনিক গল্পের নমুনা নম্বর {index}।",
                consent_given=True,
            )
            moderate_story(story, self.publisher, Story.Status.APPROVED)
        response = self.client.get(reverse("home"), {"category": "life", "page": 2})
        self.assertEqual(response.context["story_page"].number, 2)
        self.assertTrue(response.context["story_page"].has_previous())
        self.assertContains(response, "category=life")

    def test_unapproved_story_detail_is_hidden(self):
        response = self.client.get(reverse("story-detail", args=[self.pending.public_id]))
        self.assertEqual(response.status_code, 404)

    def test_submission_requires_csrf_and_is_pending(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get(reverse("submit-story"))
        csrf_token = page.cookies["csrftoken"].value
        response = client.post(
            reverse("submit-story"),
            {
                "csrfmiddlewaretoken": csrf_token,
                "category": self.category.pk,
                "content": "এটি নতুন একটি কাল্পনিক অনুভূতির গল্প।",
                "consent_given": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Story.objects.filter(content="এটি নতুন একটি কাল্পনিক অনুভূতির গল্প।", status=Story.Status.PENDING).exists())

    def test_submission_without_consent_does_not_save(self):
        self.client.post(
            reverse("submit-story"),
            {"category": self.category.pk, "content": "এটি নতুন একটি কাল্পনিক অনুভূতির গল্প।"},
        )
        self.assertFalse(Story.objects.filter(content="এটি নতুন একটি কাল্পনিক অনুভূতির গল্প।").exists())

    def test_report_creates_queue_item(self):
        response = self.client.post(
            reverse("report", args=[self.approved.public_id]),
            {"reason": Report.Reason.PERSONAL, "details": "একটি যাচাইয়ের নমুনা।"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Report.objects.filter(story=self.approved).exists())
        self.assertEqual(Report.objects.get(story=self.approved).story_public_id, self.approved.public_id)

    def test_deletion_request_has_a_moderation_workflow(self):
        self.client.post(
            reverse("deletion-request"),
            {"story_public_id": str(self.approved.public_id), "reason": "অনুরোধের নমুনা"},
        )
        self.assertTrue(DeletionRequest.objects.filter(story=self.approved, status=DeletionRequest.Status.PENDING).exists())

    def test_information_pages_and_share_card_are_available(self):
        for name in ("about", "privacy", "guidelines", "contact"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        card = self.client.get(reverse("share-card", args=[self.approved.public_id]))
        self.assertEqual(card.status_code, 200)
        self.assertEqual(card["Content-Type"], "image/png")
        self.assertTrue(card.content.startswith(b"\x89PNG"))

    def test_story_page_has_open_graph_metadata(self):
        response = self.client.get(reverse("story-detail", args=[self.approved.public_id]))
        self.assertContains(response, 'property="og:image"')
        self.assertContains(response, "facebook.com/sharer/sharer.php")

    def test_story_markup_is_rendered_as_text(self):
        self.approved.content = "<script>alert('xss')</script> এটি কেবল একটি নিরাপদ টেমপ্লেট পরীক্ষার নমুনা।"
        self.approved.save(update_fields=("content",))
        response = self.client.get(reverse("story-detail", args=[self.approved.public_id]))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert")

    def test_unknown_route_uses_branded_404(self):
        response = self.client.get("/not-a-real-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "৪০৪", status_code=404)

    def test_invalid_host_is_rejected(self):
        response = self.client.get("/", HTTP_HOST="untrusted.example")
        self.assertEqual(response.status_code, 400)


class ModeratorViewTests(TestCase):
    def setUp(self):
        self.category, _ = Category.objects.get_or_create(slug="life", defaults={"name": "জীবন"})
        self.story = Story.objects.create(category=self.category, content="মডারেশনের জন্য একটি কাল্পনিক গল্প।", consent_given=True)
        self.moderator = get_user_model().objects.create_user(username="moderator", password="test-password", is_staff=True)

    def test_anonymous_user_cannot_open_moderation_queue(self):
        response = self.client.get(reverse("moderation"))
        self.assertEqual(response.status_code, 302)

    def test_staff_approval_publishes_and_logs_story(self):
        self.client.force_login(self.moderator)
        response = self.client.post(reverse("moderate", args=[self.story.public_id]), {"action": "approve", "note": "ok"})
        self.assertEqual(response.status_code, 302)
        self.story.refresh_from_db()
        self.assertEqual(self.story.status, Story.Status.APPROVED)
        self.assertEqual(self.story.moderation_logs.count(), 1)

    def test_analytics_is_staff_only(self):
        response = self.client.get(reverse("analytics"))
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.moderator)
        self.assertEqual(self.client.get(reverse("analytics")).status_code, 200)

    def test_analytics_surfaces_old_published_stories_for_review(self):
        stale = Story.objects.create(
            category=self.category,
            content="বার্ষিক পর্যালোচনার জন্য একটি কাল্পনিক গল্প।",
            consent_given=True,
            created_at=timezone.now() - timedelta(days=366),
        )
        moderate_story(stale, self.moderator, Story.Status.APPROVED)
        self.client.force_login(self.moderator)
        response = self.client.get(reverse("analytics"))
        self.assertEqual(response.context["stories_for_review"], 1)
        self.assertContains(response, "পুনঃপর্যালোচনায় সরান ও মুছুন")


class SecurityTests(TestCase):
    def test_security_headers_are_present(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["Referrer-Policy"], "strict-origin-when-cross-origin")

    @override_settings(DEBUG=False)
    def test_branded_500_template_renders(self):
        from stories.views import server_error

        response = server_error(RequestFactory().get("/"))
        self.assertEqual(response.status_code, 500)
        self.assertIn("একটু বিরতি নিচ্ছি".encode(), response.content)
