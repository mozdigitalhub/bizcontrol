from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0006_business_metadata_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="legal_name",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="business",
            name="commercial_registration",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AlterField(
            model_name="business",
            name="nuit",
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddConstraint(
            model_name="business",
            constraint=models.UniqueConstraint(
                condition=Q(nuit__isnull=False) & ~Q(nuit=""),
                fields=("nuit",),
                name="unique_business_nuit",
            ),
        ),
    ]
