from django.contrib import admin
from django.urls import include, path

handler404 = "stories.views.not_found"
handler500 = "stories.views.server_error"

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("stories.urls")),
]
