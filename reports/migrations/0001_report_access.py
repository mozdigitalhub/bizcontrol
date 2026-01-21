from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ReportAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(blank=True, max_length=120)),
            ],
            options={
                "permissions": [
                    ("view_basic", "Pode ver relatorios basicos"),
                    ("view_finance", "Pode ver relatorios financeiros"),
                    ("view_stock", "Pode ver relatorios de stock"),
                    ("export", "Pode exportar relatorios"),
                ],
            },
        ),
    ]
