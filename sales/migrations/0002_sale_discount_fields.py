from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="sale",
            name="discount_type",
            field=models.CharField(
                choices=[
                    ("none", "Sem desconto"),
                    ("fixed", "Valor fixo"),
                    ("percent", "Percentagem"),
                ],
                default="none",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="sale",
            name="discount_value",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="sale",
            name="discount_total",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
    ]
