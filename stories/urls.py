from django.urls import path

from . import api
from . import views

urlpatterns = [
    path("api/categories/", api.categories, name="api-categories"),
    path("api/stories/", api.story_list, name="api-story-list"),
    path("api/stories/create/", api.story_create, name="api-story-create"),
    path("api/stories/<uuid:public_id>/", api.story_detail, name="api-story-detail"),
    path("api/stories/<uuid:public_id>/reactions/", api.story_react, name="api-story-react"),
    path("api/stories/<uuid:public_id>/reports/", api.story_report, name="api-story-report"),
    path("api/stories/<uuid:public_id>/deletion-requests/", api.story_deletion_request, name="api-story-deletion-request"),
    path("", views.home, name="home"),
    path("submit/", views.submit_story, name="submit-story"),
    path("story/<uuid:public_id>/", views.story_detail, name="story-detail"),
    path("story/<uuid:public_id>/react/", views.react, name="react"),
    path("story/<uuid:public_id>/report/", views.report_story, name="report"),
    path("story/<uuid:public_id>/share-card.png", views.share_card, name="share-card"),
    path("deletion-request/", views.request_deletion, name="deletion-request"),
    path("about/", views.informational_page, {"page": "about"}, name="about"),
    path("privacy/", views.informational_page, {"page": "privacy"}, name="privacy"),
    path("guidelines/", views.informational_page, {"page": "guidelines"}, name="guidelines"),
    path("contact/", views.informational_page, {"page": "contact"}, name="contact"),
    path("community/moderation/", views.moderation_dashboard, name="moderation"),
    path("community/moderation/<uuid:public_id>/", views.moderate, name="moderate"),
    path("community/moderation/report/<int:report_id>/", views.resolve_report, name="resolve-report"),
    path("community/moderation/deletion/<int:request_id>/", views.resolve_deletion, name="resolve-deletion"),
    path("community/analytics/", views.analytics_dashboard, name="analytics"),
]
