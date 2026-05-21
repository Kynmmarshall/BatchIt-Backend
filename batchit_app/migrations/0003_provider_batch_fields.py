import django.db.models.deletion
from django.db import migrations, models


def set_provider_status_from_verified(apps, schema_editor):
    Provider = apps.get_model('batchit_app', 'Provider')
    Provider.objects.filter(verified=True).update(status='verified')
    Provider.objects.filter(verified=False).update(status='pending')


class Migration(migrations.Migration):

    dependencies = [
        ('batchit_app', '0002_emailverificationcode'),
    ]

    operations = [
        # Provider: add missing fields
        migrations.AddField(
            model_name='provider',
            name='owner_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='provider',
            name='owner_email',
            field=models.EmailField(blank=True, default='', max_length=254),
        ),
        migrations.AddField(
            model_name='provider',
            name='phone',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='provider',
            name='address',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='provider',
            name='registration_number',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='provider',
            name='latitude',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='provider',
            name='longitude',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='provider',
            name='status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('verified', 'Verified'), ('rejected', 'Rejected')],
                default='pending',
                max_length=20,
            ),
        ),
        # Data migration: set status from existing verified flag
        migrations.RunPython(
            set_provider_status_from_verified,
            reverse_code=migrations.RunPython.noop,
        ),
        # Batch: make product and provider nullable (batch can exist without pre-existing product/provider)
        migrations.AlterField(
            model_name='batch',
            name='product',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='batches',
                to='batchit_app.product',
            ),
        ),
        migrations.AlterField(
            model_name='batch',
            name='provider',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='batches',
                to='batchit_app.provider',
            ),
        ),
        # Batch: add cached product_name string
        migrations.AddField(
            model_name='batch',
            name='product_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        # Batch: change quantity fields from int to float
        migrations.AlterField(
            model_name='batch',
            name='total_quantity',
            field=models.FloatField(default=0),
        ),
        migrations.AlterField(
            model_name='batch',
            name='filled_quantity',
            field=models.FloatField(default=0),
        ),
        # Batch: add missing fields
        migrations.AddField(
            model_name='batch',
            name='location_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='batch',
            name='image_url',
            field=models.URLField(blank=True, null=True),
        ),
    ]
