from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0010_document_sequence"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="allow_over_delivery_deposit",
            field=models.BooleanField(default=False),
        ),
    ]
