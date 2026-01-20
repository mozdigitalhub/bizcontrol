from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0002_alter_business_vat_rate"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="business_type",
            field=models.CharField(
                choices=[
                    ("general", "Negocio geral"),
                    ("hardware", "Ferragem / construcao"),
                    ("workshop", "Oficina mecanica"),
                    ("restaurant", "Restaurante / hamburgueria"),
                    ("grocery", "Mini-mercearia / cantina"),
                    ("clothing", "Loja de roupa"),
                    ("electric", "Material eletrico / mecanico"),
                ],
                default="general",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="business",
            name="modules_enabled",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
