from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('batchit_app', '0007_notification_batch_joined'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(choices=[('batch_created', 'Batch Created'), ('batch_joined', 'Batch Joined'), ('batch_full', 'Batch Full'), ('provider_review', 'Provider Review'), ('provider_approved', 'Provider Approved'), ('provider_rejected', 'Provider Rejected'), ('provider_message', 'Provider Message'), ('general', 'General')], default='general', max_length=30),
        ),
    ]