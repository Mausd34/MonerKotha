from django.db import migrations


CATEGORIES = (
    ("love", "প্রেম", "💗", "ভালোবাসা, মায়া আর মনের দ্বিধা"),
    ("friendship", "বন্ধুত্ব", "🤝", "পাশে থাকার গল্প"),
    ("family", "পরিবার", "🏡", "পরিবারের টানাপোড়েন ও মমতা"),
    ("campus", "ক্যাম্পাস", "🎓", "ক্যাম্পাস জীবনের স্মৃতি"),
    ("life", "জীবন", "🌿", "বেঁচে থাকার ছোট-বড় অনুভূতি"),
    ("funny", "মজার ঘটনা", "😄", "হাসির ও মজার মুহূর্ত"),
)


def add_categories(apps, schema_editor):
    Category = apps.get_model("stories", "Category")
    for order, (slug, name, emoji, description) in enumerate(CATEGORIES):
        Category.objects.using(schema_editor.connection.alias).update_or_create(
            slug=slug,
            defaults={"name": name, "emoji": emoji, "description": description, "is_active": True, "sort_order": order},
        )


def remove_categories(apps, schema_editor):
    Category = apps.get_model("stories", "Category")
    Category.objects.using(schema_editor.connection.alias).filter(slug__in=[row[0] for row in CATEGORIES]).delete()


class Migration(migrations.Migration):
    dependencies = [("stories", "0001_initial")]

    operations = [migrations.RunPython(add_categories, remove_categories)]
