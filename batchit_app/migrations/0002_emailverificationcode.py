# Generated migration for EmailVerificationCode model

from django.db import migrations, models
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('batchit_app', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailVerificationCode',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('code', models.CharField(db_index=True, max_length=6)),
                ('is_used', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
