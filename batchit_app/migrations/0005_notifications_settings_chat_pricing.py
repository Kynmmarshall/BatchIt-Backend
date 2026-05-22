import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('batchit_app', '0004_provider_ordering'),
    ]

    operations = [
        # --- Batch pricing fields ---
        migrations.AddField(
            model_name='batch',
            name='provider_unit_price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='batch',
            name='provider_savings',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),

        # --- Notification model ---
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=255)),
                ('body', models.TextField()),
                ('notification_type', models.CharField(
                    choices=[
                        ('batch_full', 'Batch Full'),
                        ('provider_approved', 'Provider Approved'),
                        ('provider_rejected', 'Provider Rejected'),
                        ('provider_message', 'Provider Message'),
                        ('general', 'General'),
                    ],
                    default='general',
                    max_length=30,
                )),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recipient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('related_batch', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='notifications',
                    to='batchit_app.batch',
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),

        # --- UserSettings model ---
        migrations.CreateModel(
            name='UserSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(default='en', max_length=10)),
                ('theme', models.CharField(default='system', max_length=20)),
                ('notif_new_batch', models.BooleanField(default=True)),
                ('notif_batch_full', models.BooleanField(default=True)),
                ('notif_provider_approval', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='settings',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),

        # --- BatchChatRoom model ---
        migrations.CreateModel(
            name='BatchChatRoom',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('batch', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chat_room',
                    to='batchit_app.batch',
                )),
            ],
        ),

        # --- ChatMember model ---
        migrations.CreateModel(
            name='ChatMember',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chat_memberships',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('room', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='members',
                    to='batchit_app.batchchatroom',
                )),
            ],
            options={
                'unique_together': {('room', 'customer')},
            },
        ),

        # --- ChatMessage model ---
        migrations.CreateModel(
            name='ChatMessage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('content', models.TextField()),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('room', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='messages',
                    to='batchit_app.batchchatroom',
                )),
                ('sender', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sent_messages',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['sent_at'],
            },
        ),
    ]
