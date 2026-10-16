from django.db import migrations


def preserve_story_ids(apps, schema_editor):
    database = schema_editor.connection.alias
    for model_name in ("ModerationLog", "Report"):
        Model = apps.get_model("stories", model_name)
        pending = []
        records = Model.objects.using(database).filter(story__isnull=False).select_related("story")
        for record in records.iterator():
            record.story_public_id = record.story.public_id
            pending.append(record)
            if len(pending) == 500:
                Model.objects.using(database).bulk_update(pending, ("story_public_id",))
                pending.clear()
        if pending:
            Model.objects.using(database).bulk_update(pending, ("story_public_id",))


class Migration(migrations.Migration):
    dependencies = [("stories", "0004_moderationlog_story_public_id_report_story_public_id_and_more")]

    operations = [migrations.RunPython(preserve_story_ids, migrations.RunPython.noop)]
