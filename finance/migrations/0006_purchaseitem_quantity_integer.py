from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0005_rename_finance_cash_business_category_idx_finance_cas_busines_23a48a_idx_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="purchaseitem",
            name="quantity",
            field=models.PositiveIntegerField(),
        ),
    ]
