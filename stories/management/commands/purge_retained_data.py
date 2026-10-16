from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from stories.models import DeletionRequest, ModerationLog, Reaction, Report, Story


class Command(BaseCommand):
    help = "Purge expired operational records; requires --execute to make changes."

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true", help="Perform the deletions.")

    def handle(self, *args, **options):
        if not options["execute"]:
            raise CommandError("No data was deleted. Rerun with --execute after reviewing the retention policy.")
        now = timezone.now()
        rejected_cutoff = now - timedelta(days=30)
        audit_cutoff = now - timedelta(days=180)
        published_cutoff = now - timedelta(days=365)
        reaction_cutoff = now - timedelta(days=90)
        counts = {
            "rejected stories": Story.objects.filter(status=Story.Status.REJECTED, moderated_at__lt=rejected_cutoff).count(),
            "old reports": Report.objects.filter(resolved_at__lt=audit_cutoff).count(),
            "old moderation logs": ModerationLog.objects.filter(created_at__lt=audit_cutoff).count(),
            "resolved deletion requests": DeletionRequest.objects.filter(resolved_at__lt=audit_cutoff).count(),
            "old reactions": Reaction.objects.filter(created_at__lt=reaction_cutoff).count(),
            "published stories for review": Story.objects.filter(
                status=Story.Status.APPROVED, created_at__lt=published_cutoff
            ).count(),
        }
        with transaction.atomic():
            Story.objects.filter(status=Story.Status.REJECTED, moderated_at__lt=rejected_cutoff).delete()
            Report.objects.filter(resolved_at__lt=audit_cutoff).delete()
            ModerationLog.objects.filter(created_at__lt=audit_cutoff).delete()
            DeletionRequest.objects.filter(resolved_at__lt=audit_cutoff).delete()
            Reaction.objects.filter(created_at__lt=reaction_cutoff).delete()
        for label, count in counts.items():
            if label == "published stories for review":
                self.stdout.write(f"{count} published story/stories are due for human review (not deleted).")
            else:
                self.stdout.write(f"Removed {count} {label}.")
