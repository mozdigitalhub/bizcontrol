from django.db import migrations


def rename_cash_method(apps, schema_editor):
    PaymentMethod = apps.get_model("finance", "PaymentMethod")
    PaymentMethod.objects.filter(code="cash", name="Dinheiro").update(
        name="Numerario"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0006_purchaseitem_quantity_integer"),
    ]

    operations = [
        migrations.RunPython(rename_cash_method, migrations.RunPython.noop),
    ]
