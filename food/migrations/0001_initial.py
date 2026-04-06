from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalog", "0003_reorder_level_integer"),
        ("customers", "0004_customer_profile_fields"),
        ("tenants", "0016_rename_tenants_ten_business_d9b7b9_idx_tenants_ten_busines_c715dc_idx"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(blank=True, max_length=30, null=True)),
                ("status", models.CharField(choices=[("draft", "Rascunho"), ("paid", "Pago"), ("in_kitchen", "Em preparacao"), ("ready", "Pronto"), ("delivered", "Entregue"), ("canceled", "Cancelado")], default="draft", max_length=20)),
                ("channel", models.CharField(choices=[("counter", "Balcao"), ("takeaway", "Takeaway"), ("delivery", "Delivery")], default="counter", max_length=20)),
                ("payment_method", models.CharField(blank=True, max_length=20)),
                ("subtotal", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("tax_total", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("total", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("business", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="food_orders", to="tenants.business")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_food_orders", to=settings.AUTH_USER_MODEL)),
                ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="customers.customer")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_food_orders", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField()),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("line_subtotal", models.DecimalField(decimal_places=2, max_digits=12)),
                ("line_tax", models.DecimalField(decimal_places=2, max_digits=12)),
                ("line_total", models.DecimalField(decimal_places=2, max_digits=12)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="food.order")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="catalog.product")),
            ],
        ),
        migrations.CreateModel(
            name="DeliveryInfo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("address", models.CharField(max_length=255)),
                ("phone", models.CharField(max_length=30)),
                ("delivery_fee", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("driver_name", models.CharField(blank=True, max_length=120)),
                ("notes", models.TextField(blank=True)),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="delivery", to="food.order")),
            ],
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["business", "created_at"], name="food_order_busines_2f6508_idx"),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["business", "status"], name="food_order_busines_77e3e8_idx"),
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.UniqueConstraint(condition=models.Q(("code__isnull", False)), fields=("business", "code"), name="uniq_food_order_code_business"),
        ),
    ]
