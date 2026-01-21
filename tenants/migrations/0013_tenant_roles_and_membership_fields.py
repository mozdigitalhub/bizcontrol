# Generated manually for RBAC models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0012_alter_documentsequence_doc_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="TenantRole",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "code",
                    models.CharField(
                        choices=[
                            ("owner_admin", "Admin da empresa"),
                            ("manager", "Gerente"),
                            ("cashier_sales", "Caixa/Vendas"),
                            ("finance", "Financeiro"),
                            ("stock_warehouse", "Stock/Armazem"),
                            ("operations_production", "Operacional/Producao"),
                            ("support_viewer", "Leitura/Suporte"),
                        ],
                        max_length=40,
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("is_system", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="roles",
                        to="tenants.business",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_tenant_roles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_tenant_roles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "permissions",
                    models.ManyToManyField(
                        blank=True, related_name="tenant_roles", to="auth.permission"
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=["business", "code"], name="uniq_tenant_role_code"
                    )
                ]
            },
        ),
        migrations.CreateModel(
            name="RoleAuditLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "target_type",
                    models.CharField(
                        choices=[("role", "Role"), ("user", "Utilizador")],
                        max_length=20,
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("update", "Atualizar"),
                            ("reset", "Reset"),
                            ("assign", "Atribuir"),
                        ],
                        max_length=20,
                    ),
                ),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_audits",
                        to="tenants.business",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="tenants.tenantrole",
                    ),
                ),
                (
                    "membership",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to="tenants.businessmembership",
                    ),
                ),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="role_audit_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["business", "created_at"], name="tenants_ro_business_8c1d7f_idx")]
            },
        ),
        migrations.AddField(
            model_name="businessmembership",
            name="role_profile",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="memberships",
                to="tenants.tenantrole",
            ),
        ),
        migrations.AddField(
            model_name="businessmembership",
            name="extra_permissions",
            field=models.ManyToManyField(
                blank=True,
                related_name="membership_extra_permissions",
                to="auth.permission",
            ),
        ),
        migrations.AddField(
            model_name="businessmembership",
            name="revoked_permissions",
            field=models.ManyToManyField(
                blank=True,
                related_name="membership_revoked_permissions",
                to="auth.permission",
            ),
        ),
        migrations.AddField(
            model_name="businessmembership",
            name="department",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="businessmembership",
            name="notes",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="businessmembership",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_memberships",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="businessmembership",
            name="updated_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="updated_memberships",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="businessmembership",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
