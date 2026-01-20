from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0003_business_type_and_modules"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="feature_flags",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
