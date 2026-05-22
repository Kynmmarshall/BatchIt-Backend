from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('batchit_app', '0003_provider_batch_fields'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='provider',
            options={'ordering': ['created_at']},
        ),
    ]