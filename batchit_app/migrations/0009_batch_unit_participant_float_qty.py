from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Two changes introduced together:

    1. batchit_app.Batch — add `unit` field (kg / g / L / mL / units / boxes).
       Existing rows default to 'kg'.

    2. batchit_app.BatchParticipant — change `quantity_requested` from
       PositiveIntegerField to FloatField so fractional quantities (e.g. 2.5 kg)
       are stored correctly.  Existing integer values are preserved as floats.
    """

    dependencies = [
        ('batchit_app', '0008_notification_provider_review'),
    ]

    operations = [
        # ── 1. Add unit to Batch ──────────────────────────────────────────────
        migrations.AddField(
            model_name='batch',
            name='unit',
            field=models.CharField(
                choices=[
                    ('kg', 'Kilograms'),
                    ('g', 'Grams'),
                    ('L', 'Litres'),
                    ('mL', 'Millilitres'),
                    ('units', 'Units/Pieces'),
                    ('boxes', 'Boxes'),
                ],
                default='kg',
                max_length=10,
            ),
        ),

        # ── 2. quantity_requested: PositiveIntegerField → FloatField ─────────
        migrations.AlterField(
            model_name='batchparticipant',
            name='quantity_requested',
            field=models.FloatField(),
        ),
    ]
