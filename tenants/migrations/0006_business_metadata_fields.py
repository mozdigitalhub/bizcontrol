from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0005_alter_business_business_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="status",
            field=models.CharField(
                choices=[("active", "Ativo"), ("inactive", "Inativo")],
                default="active",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="business",
            name="country",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="business",
            name="city",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="business",
            name="currency",
            field=models.CharField(default="MZN", max_length=10),
        ),
        migrations.AddField(
            model_name="business",
            name="timezone",
            field=models.CharField(default="Africa/Maputo", max_length=60),
        ),
    ]
