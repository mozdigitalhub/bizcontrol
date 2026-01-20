from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0009_rename_tenants_ten_business_b1eaa5_idx_tenants_ten_busines_f76f8d_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("doc_type", models.CharField(choices=[("sale", "Venda"), ("invoice", "Fatura"), ("receipt", "Recibo"), ("delivery", "Guia de entrega")], max_length=20)),
                ("seq_date", models.DateField()),
                ("current_value", models.PositiveIntegerField(default=0)),
                ("business", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="document_sequences", to="tenants.business")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("business", "doc_type", "seq_date"), name="uniq_document_sequence")
                ],
            },
        ),
    ]
