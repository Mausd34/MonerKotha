from django.core.management.base import BaseCommand
from django.utils import timezone

from stories.models import Category, DailyPrompt, Story


SAMPLES = (
    ("প্রেম", "একটা পুরোনো চিঠি আজও বইয়ের পাতায় রেখে দিয়েছি। মানুষটা নেই, কিন্তু সেই সময়ের যত্নটুকু মনে পড়লে মনটা নরম হয়ে যায়।"),
    ("বন্ধুত্ব", "পরীক্ষার আগের রাতে বন্ধুটি নিজের পড়া থামিয়ে আমার সঙ্গে বসেছিল। ফল যা-ই হোক, সেই পাশে থাকাটাই আমার কাছে বড় ছিল।"),
    ("পরিবার", "প্রতিদিন বাড়ি থেকে ফোন আসে, আমি ঠিকমতো খেয়েছি কি না জানতে। দূরে থাকি বলে এখন বুঝি, এই ছোট প্রশ্নের ভেতর কতখানি মায়া লুকিয়ে থাকে।"),
    ("ক্যাম্পাস", "ক্যাম্পাসের শেষ বিকেলে সবাই ছবি তুলছিল। আমি চুপচাপ মাঠটার দিকে তাকিয়ে ছিলাম—এখানেই তো প্রথম নিজের মতো করে বাঁচতে শিখেছি।"),
    ("জীবন", "একদিনে সব ঠিক হয়নি। শুধু আজকে কালকের চেয়ে একটু সহজ ছিল। আপাতত এইটুকুই আমার কাছে অনেক।"),
    ("মজার ঘটনা", "অনলাইন ক্লাসে মাইক বন্ধ ভেবে নিজের বিড়ালকে বক্তৃতা দিচ্ছিলাম। শিক্ষক শেষে বললেন, বিড়ালটির যুক্তি বেশ ভালো ছিল!"),
)


class Command(BaseCommand):
    help = "Add clearly fictional, unpublished sample stories for local demonstration."

    def add_arguments(self, parser):
        parser.add_argument("--approve", action="store_true", help="Automatically approve the demo stories.")

    def handle(self, *args, **options):
        auto_approve = options.get("approve", False)
        created = 0
        for category_name, content in SAMPLES:
            category = Category.objects.get(name=category_name)
            story, was_created = Story.objects.get_or_create(
                category=category,
                content=content,
                is_demo=True,
                defaults={
                    "status": Story.Status.APPROVED if auto_approve else Story.Status.PENDING,
                    "consent_given": True,
                },
            )
            if auto_approve and story.status != Story.Status.APPROVED:
                story.status = Story.Status.APPROVED
                story.save(update_fields=("status",))
            created += int(was_created)
        DailyPrompt.objects.update_or_create(
            active_date=timezone.localdate(),
            defaults={"prompt": "যে কথাটা কাউকে বলা হয়নি—আজ সেটা লিখে ফেলুন।", "is_active": True},
        )
        state_label = "approved" if auto_approve else "pending"
        self.stdout.write(self.style.SUCCESS(f"{created} fictional sample story/stories added as {state_label}."))
