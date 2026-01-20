from django.db import migrations


def forwards(apps, schema_editor):
    Sale = apps.get_model("sales", "Sale")
    Sale.objects.filter(status="confirmed").update(delivery_status="delivered")


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0005_sale_delivery_mode_sale_delivery_status_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
