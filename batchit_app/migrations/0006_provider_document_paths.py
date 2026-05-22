from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('batchit_app', '0005_notifications_settings_chat_pricing'),
    ]

    operations = [
        migrations.AddField(
            model_name='provider',
            name='document_paths',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
