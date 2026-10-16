import json
from json import JSONDecodeError

from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import DeletionRequestForm, ReportForm, StorySubmissionForm
from .models import Category, DailyPrompt, DeletionRequest, Reaction, Report, Story
from .services import allow_request, visitor_hash


def _error(message, code, status, fields=None):
    error = {"code": code, "message": message}
    if fields is not None:
        error["fields"] = fields
    return JsonResponse({"error": error}, status=status)


def _json_data(request):
    if request.content_type != "application/json":
        return None, _error("Content-Type must be application/json.", "unsupported_media_type", 415)
    try:
        data = json.loads(request.body)
    except (JSONDecodeError, UnicodeDecodeError):
        return None, _error("Request body must contain valid JSON.", "invalid_json", 400)
    if not isinstance(data, dict):
        return None, _error("JSON request body must be an object.", "invalid_json_shape", 400)
    return data, None


def _serialize_category(category):
    return {
        "slug": category.slug,
        "name": category.name,
        "emoji": category.emoji,
        "description": category.description,
    }


def _serialize_story(story):
    return {
        "id": str(story.public_id),
        "content": story.content,
        "category": _serialize_category(story.category),
        "reaction_count": story.reaction_count,
        "created_at": story.created_at.isoformat(),
    }


@require_GET
def categories(request):
    items = Category.objects.filter(is_active=True)
    return JsonResponse({"results": [_serialize_category(item) for item in items]})


@require_GET
def story_list(request):
    stories = (
        Story.objects.filter(status=Story.Status.APPROVED, category__is_active=True)
        .select_related("category")
        .annotate(_reaction_count=Count("reactions"))
    )
    category_slug = request.GET.get("category", "").strip()
    query = request.GET.get("q", "").strip()[:100]
    sort = request.GET.get("sort", "latest")
    if sort not in {"latest", "popular"}:
        return _error("sort must be either 'latest' or 'popular'.", "invalid_sort", 400)
    if category_slug:
        if not Category.objects.filter(slug=category_slug, is_active=True).exists():
            return _error("The requested category does not exist.", "invalid_category", 400)
        stories = stories.filter(category__slug=category_slug)
    if query:
        stories = stories.filter(content__icontains=query)
    if sort == "popular":
        stories = stories.order_by("-_reaction_count", "-created_at", "-id")
    else:
        stories = stories.order_by("-created_at", "-id")

    page = Paginator(stories, 12).get_page(request.GET.get("page"))
    return JsonResponse(
        {
            "count": page.paginator.count,
            "page": page.number,
            "pages": page.paginator.num_pages,
            "next": page.next_page_number() if page.has_next() else None,
            "previous": page.previous_page_number() if page.has_previous() else None,
            "results": [_serialize_story(story) for story in page.object_list],
        }
    )


@require_GET
def story_detail(request, public_id):
    story = get_object_or_404(
        Story.objects.filter(status=Story.Status.APPROVED, category__is_active=True)
        .select_related("category")
        .annotate(_reaction_count=Count("reactions")),
        public_id=public_id,
    )
    return JsonResponse({"result": _serialize_story(story)})


@require_POST
def story_create(request):
    if not allow_request(request, "submit", 3, 3600):
        return _error("Submission rate limit exceeded.", "rate_limited", 429)
    data, error = _json_data(request)
    if error:
        return error
    form = StorySubmissionForm(data)
    if not form.is_valid():
        return _error("Story submission is invalid.", "validation_error", 400, form.errors.get_json_data())
    story = form.save()
    return JsonResponse(
        {
            "result": {
                "id": str(story.public_id),
                "status": story.status,
                "message": "Your story has been submitted for moderation.",
            }
        },
        status=201,
    )


@require_POST
def story_react(request, public_id):
    story = get_object_or_404(Story, public_id=public_id, status=Story.Status.APPROVED)
    data, error = _json_data(request)
    if error:
        return error
    kind = data.get("kind", "")
    if kind not in Reaction.Kind.values:
        return _error("kind must be one of the supported reaction values.", "invalid_reaction", 400)
    if not allow_request(request, "reaction", 30, 3600):
        return _error("Reaction rate limit exceeded.", "rate_limited", 429)
    identity = visitor_hash(request)
    if not identity:
        return _error("The request could not be verified.", "invalid_visitor", 400)
    _, created = Reaction.objects.get_or_create(story=story, kind=kind, visitor_hash=identity)
    return JsonResponse({"result": {"created": created, "reaction_count": story.reactions.count()}})


@require_POST
def story_report(request, public_id):
    story = get_object_or_404(Story, public_id=public_id, status=Story.Status.APPROVED)
    if not allow_request(request, "report", 5, 3600):
        return _error("Report rate limit exceeded.", "rate_limited", 429)
    data, error = _json_data(request)
    if error:
        return error
    form = ReportForm(data)
    if not form.is_valid():
        return _error("Report is invalid.", "validation_error", 400, form.errors.get_json_data())
    report = form.save(commit=False)
    report.story = story
    report.story_public_id = story.public_id
    report.save()
    return JsonResponse({"result": {"message": "Your report has been received."}}, status=201)


@require_POST
def story_deletion_request(request, public_id):
    story = get_object_or_404(Story, public_id=public_id, status=Story.Status.APPROVED)
    if not allow_request(request, "deletion", 3, 86400):
        return _error("Deletion request rate limit exceeded.", "rate_limited", 429)
    data, error = _json_data(request)
    if error:
        return error
    data["story_public_id"] = str(story.public_id)
    form = DeletionRequestForm(data)
    if not form.is_valid():
        return _error("Deletion request is invalid.", "validation_error", 400, form.errors.get_json_data())
    DeletionRequest.objects.create(
        story=story,
        story_public_id=story.public_id,
        reason=form.cleaned_data["reason"],
    )
    return JsonResponse({"result": {"message": "Your deletion request has been received."}}, status=202)
