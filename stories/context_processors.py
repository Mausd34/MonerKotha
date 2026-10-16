from django.conf import settings


def site_config(request):
    return {"support_email": settings.SUPPORT_EMAIL}
