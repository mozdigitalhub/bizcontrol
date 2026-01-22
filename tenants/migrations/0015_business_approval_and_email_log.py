from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0014_rename_tenants_ro_business_8c1d7f_idx_tenants_rol_busines_5c44e6_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="registered_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="business",
            name="registration_ip",
            field=models.CharField(blank=True, max_length=45),
        ),
        migrations.AddField(
            model_name="business",
            name="approval_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="business",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="business",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="approved_businesses",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="business",
            name="rejected_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="business",
            name="rejected_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="rejected_businesses",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="business",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pendente"),
                    ("active", "Ativo"),
                    ("inactive", "Inativo"),
                    ("rejected", "Rejeitado"),
                ],
                default="active",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="TenantEmailLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email_type", models.CharField(choices=[("pending", "Registo pendente"), ("approved", "Aprovacao"), ("rejected", "Rejeicao")], max_length=20)),
                ("recipient", models.EmailField(max_length=254)),
                ("subject", models.CharField(max_length=200)),
                ("status", models.CharField(choices=[("sent", "Enviado"), ("failed", "Falhou")], max_length=20)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("business", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="email_logs", to="tenants.business")),
                ("sent_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tenant_email_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["business", "email_type"], name="tenants_ten_business_d9b7b9_idx"),
                ],
            },
        ),
    ]
