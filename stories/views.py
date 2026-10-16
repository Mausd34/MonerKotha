import os
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from textwrap import wrap
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from PIL import Image, ImageDraw, ImageFont

from .forms import DeletionRequestForm, ReportForm, StorySubmissionForm
from .models import Category, DailyPrompt, DeletionRequest, Reaction, Report, Story
from .services import allow_request, moderate_story, visitor_hash


def home(request):
    stories = Story.objects.filter(status=Story.Status.APPROVED).select_related("category").annotate(
        _reaction_count=Count("reactions")
    )
    category_slug = request.GET.get("category", "").strip()
    query = request.GET.get("q", "").strip()[:100]
    sort = request.GET.get("sort", "latest")
    if category_slug:
        stories = stories.filter(category__slug=category_slug, category__is_active=True)
    if query:
        stories = stories.filter(content__icontains=query)
    if sort == "popular":
        stories = stories.order_by("-_reaction_count", "-created_at", "-id")
    else:
        stories = stories.order_by("-created_at", "-id")
    prompt = DailyPrompt.objects.filter(active_date=timezone.localdate(), is_active=True).first()
    if prompt is None:
        prompt = DailyPrompt.objects.filter(is_active=True, active_date__lte=timezone.localdate()).first()
    story_page = Paginator(stories, 12).get_page(request.GET.get("page"))
    return render(
        request,
        "stories/home.html",
        {
            "stories": story_page.object_list,
            "story_page": story_page,
            "categories": Category.objects.filter(is_active=True),
            "selected_category": category_slug,
            "search_query": query,
            "sort": sort if sort in {"latest", "popular"} else "latest",
            "daily_prompt": prompt,
        },
    )


def submit_story(request):
    if request.method == "POST":
        if not allow_request(request, "submit", 3, 3600):
            return render(request, "stories/submit.html", {"form": StorySubmissionForm(request.POST), "rate_limited": True}, status=429)
        form = StorySubmissionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "আপনার গল্পটি পেয়েছি। পর্যালোচনা শেষে উপযুক্ত হলে প্রকাশ করা হবে।")
            return redirect("home")
    else:
        form = StorySubmissionForm()
    return render(request, "stories/submit.html", {"form": form})


def story_detail(request, public_id):
    story = get_object_or_404(
        Story.objects.filter(status=Story.Status.APPROVED)
        .select_related("category")
        .annotate(_reaction_count=Count("reactions")),
        public_id=public_id,
    )
    return render(
        request,
        "stories/detail.html",
        {
            "story": story,
            "report_form": ReportForm(),
            "deletion_form": DeletionRequestForm(initial={"story_public_id": story.public_id}),
            "facebook_share_url": "https://www.facebook.com/sharer/sharer.php?u="
            + quote(request.build_absolute_uri(reverse("story-detail", args=(story.public_id,))), safe=""),
            "visitor_reactions": list(
                Reaction.objects.filter(story=story, visitor_hash=visitor_hash(request)).values_list("kind", flat=True)
            )
            if visitor_hash(request)
            else [],
        },
    )


@require_POST
def react(request, public_id):
    story = get_object_or_404(Story, public_id=public_id, status=Story.Status.APPROVED)
    kind = request.POST.get("kind", "")
    if kind not in Reaction.Kind.values:
        return HttpResponse("Invalid reaction.", status=400)
    if not allow_request(request, "reaction", 30, 3600):
        return HttpResponse("আজকের প্রতিক্রিয়ার সীমা পূর্ণ হয়েছে।", status=429)
    identity = visitor_hash(request)
    if not identity:
        return HttpResponse("এই অনুরোধটি যাচাই করা যায়নি।", status=400)
    try:
        Reaction.objects.create(story=story, kind=kind, visitor_hash=identity)
    except IntegrityError:
        pass
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return HttpResponse(str(story.reactions.count()), content_type="text/plain; charset=utf-8")
    return redirect("story-detail", public_id=story.public_id)


@require_POST
def report_story(request, public_id):
    story = get_object_or_404(Story, public_id=public_id, status=Story.Status.APPROVED)
    if not allow_request(request, "report", 5, 3600):
        messages.error(request, "অনেকগুলো প্রতিবেদন জমা হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করুন।")
        return redirect("story-detail", public_id=story.public_id)
    form = ReportForm(request.POST)
    if form.is_valid():
        report = form.save(commit=False)
        report.story = story
        report.story_public_id = story.public_id
        report.save()
        messages.success(request, "প্রতিবেদনটি পেয়েছি। আমাদের মডারেশন টিম পর্যালোচনা করবে।")
    else:
        messages.error(request, "প্রতিবেদন পাঠানো যায়নি। কারণটি বেছে আবার চেষ্টা করুন।")
    return redirect("story-detail", public_id=story.public_id)


@require_POST
def request_deletion(request):
    form = DeletionRequestForm(request.POST)
    if not form.is_valid():
        messages.error(request, "অনুরোধটি সঠিকভাবে জমা হয়নি।")
        return redirect("home")
    public_id = form.cleaned_data["story_public_id"]
    if not allow_request(request, "deletion", 3, 86400):
        messages.error(request, "অনেকগুলো অনুরোধ জমা হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করুন।")
        return redirect("home")
    story = Story.objects.filter(public_id=public_id, status=Story.Status.APPROVED).first()
    if not story:
        messages.error(request, "প্রকাশিত গল্পটি খুঁজে পাওয়া যায়নি।")
        return redirect("home")
    DeletionRequest.objects.create(story=story, story_public_id=public_id, reason=form.cleaned_data["reason"])
    messages.success(request, "গল্প সরানোর অনুরোধ পেয়েছি। আমাদের টিম যাচাই করে ব্যবস্থা নেবে।")
    return redirect("story-detail", public_id=public_id)


def share_card(request, public_id):
    story = get_object_or_404(Story.objects.select_related("category"), public_id=public_id, status=Story.Status.APPROVED)
    configured_font = os.environ.get("SHARE_CARD_FONT") or ""
    candidates = [
        configured_font,
        str(settings.BASE_DIR / "static" / "fonts" / "NotoSansBengali-Regular.ttf"),
        r"C:\Windows\Fonts\Nirmala.ttf",
        r"C:\Windows\Fonts\NirmalaB.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    bold_candidates = [
        str(settings.BASE_DIR / "static" / "fonts" / "NotoSansBengali-Bold.ttf"),
        r"C:\Windows\Fonts\Nirmala.ttf",
        r"C:\Windows\Fonts\NirmalaB.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    font_path = next((path for path in candidates if path and Path(path).is_file()), None)
    bold_font_path = next((path for path in bold_candidates if path and Path(path).is_file()), font_path)
    try:
        image = Image.new("RGB", (1080, 1350), "#fff9f6")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((64, 64, 1016, 1286), radius=48, fill="#21172f")
        draw.rounded_rectangle((104, 104, 976, 1246), radius=34, fill="#fff9f6")
        if font_path and bold_font_path:
            title_font = ImageFont.truetype(bold_font_path, 42)
            body_font = ImageFont.truetype(font_path, 38)
            brand_font = ImageFont.truetype(font_path, 30)
        else:
            title_font = body_font = brand_font = ImageFont.load_default()
        draw.text((154, 168), "মনেরকথা  ·  " + story.category.name, font=title_font, fill="#e94e8b")
        lines = []
        for paragraph in story.content.splitlines():
            lines.extend(wrap(paragraph, width=27, break_long_words=True) or [""])
        y = 340
        for line in lines[:12]:
            draw.text((154, y), line, font=body_font, fill="#21172f")
            y += 68
        draw.text((154, 1114), "নাম নয়, অনুভূতিই আসল পরিচয়।", font=brand_font, fill="#735b87")
        draw.text((154, 1172), "monerkotha · মনের কথা ভাগ করে নিন", font=brand_font, fill="#735b87")
    except (OSError, ValueError) as exc:
        return HttpResponse(f"Share card could not be generated: {exc}", status=503)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    response = HttpResponse(output.getvalue(), content_type="image/png")
    response["Cache-Control"] = "public, max-age=86400"
    return response


def informational_page(request, page):
    if page not in {"about", "privacy", "guidelines", "contact"}:
        raise Http404
    return render(request, f"stories/{page}.html")


@staff_member_required
def moderation_dashboard(request):
    pending = Story.objects.filter(status=Story.Status.PENDING).select_related("category").order_by("created_at")
    reports = Report.objects.filter(is_resolved=False).select_related("story", "story__category").order_by("-created_at")
    deletions = DeletionRequest.objects.filter(status=DeletionRequest.Status.PENDING).select_related("story")
    return render(
        request,
        "stories/moderation.html",
        {
            "pending_stories": pending[:100],
            "pending_count": pending.count(),
            "reports": reports[:100],
            "report_count": reports.count(),
            "deletion_requests": deletions[:100],
            "deletion_count": deletions.count(),
        },
    )


@staff_member_required
@require_POST
def moderate(request, public_id):
    story = get_object_or_404(Story, public_id=public_id)
    action = request.POST.get("action")
    status_map = {
        "approve": Story.Status.APPROVED,
        "reject": Story.Status.REJECTED,
        "remove": Story.Status.REMOVED,
    }
    if action not in status_map:
        messages.error(request, "অজানা মডারেশন সিদ্ধান্ত।")
        return redirect("moderation")
    try:
        moderate_story(story, request.user, status_map[action], request.POST.get("note", ""))
    except ValueError:
        messages.error(request, "গল্পটির বর্তমান অবস্থার জন্য এই সিদ্ধান্তটি প্রযোজ্য নয়।")
        return redirect("moderation")
    messages.success(request, "মডারেশন সিদ্ধান্ত সংরক্ষণ করা হয়েছে।")
    return redirect("moderation")


@staff_member_required
@require_POST
@transaction.atomic
def resolve_report(request, report_id):
    report = get_object_or_404(Report, pk=report_id)
    report.is_resolved = True
    report.resolved_at = timezone.now()
    report.save(update_fields=("is_resolved", "resolved_at"))
    action = request.POST.get("action")
    if action == "remove" and report.story and report.story.status != Story.Status.REMOVED:
        moderate_story(report.story, request.user, Story.Status.REMOVED, "প্রতিবেদনের ভিত্তিতে সরানো হয়েছে")
    messages.success(request, "প্রতিবেদনটি পর্যালোচনা করা হয়েছে।")
    return redirect("moderation")


@staff_member_required
@require_POST
@transaction.atomic
def resolve_deletion(request, request_id):
    deletion = get_object_or_404(DeletionRequest, pk=request_id, status=DeletionRequest.Status.PENDING)
    if request.POST.get("action") == "approve":
        deletion.status = DeletionRequest.Status.COMPLETED
        if deletion.story and deletion.story.status != Story.Status.REMOVED:
            moderate_story(deletion.story, request.user, Story.Status.REMOVED, "লেখকের সরানোর অনুরোধ")
    else:
        deletion.status = DeletionRequest.Status.DECLINED
    deletion.resolved_at = timezone.now()
    deletion.save(update_fields=("status", "resolved_at"))
    messages.success(request, "সরানোর অনুরোধের সিদ্ধান্ত সংরক্ষিত হয়েছে।")
    return redirect("moderation")


@staff_member_required
def analytics_dashboard(request):
    today = timezone.localdate()
    since = timezone.now() - timedelta(days=30)
    review_cutoff = timezone.now() - timedelta(days=365)
    daily = (
        Story.objects.filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    return render(
        request,
        "stories/analytics.html",
        {
            "total_approved": Story.objects.filter(status=Story.Status.APPROVED).count(),
            "pending_count": Story.objects.filter(status=Story.Status.PENDING).count(),
            "reports_open": Report.objects.filter(is_resolved=False).count(),
            "stories_today": Story.objects.filter(created_at__date=today).count(),
            "stories_for_review": Story.objects.filter(
                status=Story.Status.APPROVED, created_at__lt=review_cutoff
            ).count(),
            "stale_stories": Story.objects.filter(
                status=Story.Status.APPROVED, created_at__lt=review_cutoff
            ).select_related("category")[:100],
            "daily_counts": daily,
        },
    )


def not_found(request, exception):
    return render(request, "404.html", status=404)


def server_error(request):
    return render(request, "500.html", status=500)
