from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from tenants.models import Business, TenantRole


CUSTOM_PERMISSION_DEFS = [
    ("manage_roles", "Pode gerir roles e permissoes"),
    ("manage_staff", "Pode gerir colaboradores"),
    ("manage_tax", "Pode gerir impostos e configuracoes fiscais"),
]

PERMISSION_CATEGORIES = [
    {"key": "sales", "label": "Vendas", "app_label": "sales"},
    {"key": "food", "label": "Pedidos/Cozinha", "app_label": "food"},
    {"key": "quotations", "label": "Cotacoes", "app_label": "quotations"},
    {"key": "customers", "label": "Clientes", "app_label": "customers"},
    {"key": "receivables", "label": "Fiado/Recebiveis", "app_label": "receivables"},
    {"key": "billing", "label": "Faturacao", "app_label": "billing"},
    {"key": "deliveries", "label": "Guias/Levantamentos", "app_label": "deliveries"},
    {"key": "inventory", "label": "Stock", "app_label": "inventory"},
    {"key": "catalog", "label": "Catalogo", "app_label": "catalog"},
    {"key": "finance", "label": "Financeiro", "app_label": "finance"},
    {"key": "reports", "label": "Relatorios", "app_label": "reports"},
    {
        "key": "settings",
        "label": "Configuracoes",
        "custom_codenames": ["manage_roles", "manage_staff", "manage_tax"],
    },
]

PERMISSION_LEVELS = {
    "view": ["view"],
    "edit": ["view", "add", "change"],
    "full": ["view", "add", "change", "delete"],
}

ROLE_BASE_PRESETS = {
    TenantRole.ROLE_OWNER_ADMIN: {
        "name": "Admin da empresa",
        "description": "Acesso total e configuracoes completas.",
        "apps": {"*": "full"},
        "custom": ["manage_roles", "manage_staff", "manage_tax"],
    },
    TenantRole.ROLE_MANAGER: {
        "name": "Gerente",
        "description": "Gestao operacional e relatatorios.",
        "apps": {
            "sales": "full",
            "food": "full",
            "quotations": "full",
            "customers": "full",
            "receivables": "full",
            "billing": "full",
            "deliveries": "full",
            "inventory": "full",
            "catalog": "full",
            "finance": "edit",
        },
        "custom": ["manage_staff"],
        "extra_permissions": [
            "reports.view_basic",
            "reports.view_finance",
            "reports.view_stock",
        ],
    },
    TenantRole.ROLE_CASHIER: {
        "name": "Caixa/Vendas",
        "description": "Registo de vendas e atendimento ao cliente.",
        "apps": {
            "sales": "edit",
            "food": "edit",
            "customers": "edit",
            "receivables": "edit",
            "billing": "view",
            "deliveries": "view",
            "catalog": "view",
        },
        "extra_permissions": ["reports.view_basic"],
    },
    TenantRole.ROLE_FINANCE: {
        "name": "Financeiro",
        "description": "Gestao financeira, pagamentos e relatatorios.",
        "apps": {
            "finance": "full",
            "billing": "view",
            "receivables": "full",
        },
        "extra_permissions": [
            "reports.view_basic",
            "reports.view_finance",
            "reports.export",
        ],
    },
    TenantRole.ROLE_STOCK: {
        "name": "Stock/Armazem",
        "description": "Controlo de stock e rececao de mercadoria.",
        "apps": {
            "inventory": "full",
            "catalog": "edit",
            "deliveries": "view",
            "finance": "view",
        },
        "extra_permissions": ["reports.view_stock"],
    },
    TenantRole.ROLE_OPERATIONS: {
        "name": "Operacional/Producao",
        "description": "Operacoes internas, levantamentos e guias.",
        "apps": {
            "deliveries": "full",
            "sales": "view",
            "inventory": "view",
        },
    },
    TenantRole.ROLE_SUPPORT: {
        "name": "Leitura/Suporte",
        "description": "Acesso apenas para consulta.",
        "apps": {
            "sales": "view",
            "food": "view",
            "quotations": "view",
            "customers": "view",
            "receivables": "view",
            "billing": "view",
            "deliveries": "view",
            "inventory": "view",
            "catalog": "view",
            "finance": "view",
        },
        "extra_permissions": ["reports.view_basic"],
    },
}

BUSINESS_TYPE_OVERRIDES = {
    Business.BUSINESS_RESTAURANT: {
        TenantRole.ROLE_MANAGER: {"apps": {"quotations": None, "deliveries": None}},
        TenantRole.ROLE_CASHIER: {"apps": {"quotations": None, "deliveries": None}},
        TenantRole.ROLE_FINANCE: {"apps": {"quotations": None}},
        TenantRole.ROLE_STOCK: {"apps": {"deliveries": None}},
        TenantRole.ROLE_OPERATIONS: {"apps": {"deliveries": None}},
        TenantRole.ROLE_SUPPORT: {"apps": {"quotations": None, "deliveries": None}},
    },
    Business.BUSINESS_BURGER: {
        TenantRole.ROLE_MANAGER: {"apps": {"quotations": None, "deliveries": None}},
        TenantRole.ROLE_CASHIER: {"apps": {"quotations": None, "deliveries": None}},
        TenantRole.ROLE_FINANCE: {"apps": {"quotations": None}},
        TenantRole.ROLE_STOCK: {"apps": {"deliveries": None}},
        TenantRole.ROLE_OPERATIONS: {"apps": {"deliveries": None}},
        TenantRole.ROLE_SUPPORT: {"apps": {"quotations": None, "deliveries": None}},
    },
    Business.BUSINESS_CLOTHING: {
        TenantRole.ROLE_MANAGER: {"apps": {"quotations": None}},
        TenantRole.ROLE_CASHIER: {"apps": {"quotations": None}},
        TenantRole.ROLE_FINANCE: {"apps": {"quotations": None}},
        TenantRole.ROLE_SUPPORT: {"apps": {"quotations": None}},
    },
    Business.BUSINESS_GROCERY: {
        TenantRole.ROLE_MANAGER: {"apps": {"quotations": None}},
        TenantRole.ROLE_CASHIER: {"apps": {"quotations": None}},
        TenantRole.ROLE_FINANCE: {"apps": {"quotations": None}},
        TenantRole.ROLE_SUPPORT: {"apps": {"quotations": None}},
    },
    Business.BUSINESS_MINI_GROCERY: {
        TenantRole.ROLE_MANAGER: {"apps": {"quotations": None}},
        TenantRole.ROLE_CASHIER: {"apps": {"quotations": None}},
        TenantRole.ROLE_FINANCE: {"apps": {"quotations": None}},
        TenantRole.ROLE_SUPPORT: {"apps": {"quotations": None}},
    },
    Business.BUSINESS_ALCOHOL: {
        TenantRole.ROLE_MANAGER: {"apps": {"quotations": None}},
        TenantRole.ROLE_CASHIER: {"apps": {"quotations": None}},
        TenantRole.ROLE_FINANCE: {"apps": {"quotations": None}},
        TenantRole.ROLE_SUPPORT: {"apps": {"quotations": None}},
    },
}


def ensure_custom_permissions():
    content_type = ContentType.objects.get_for_model(Business)
    created = []
    for codename, name in CUSTOM_PERMISSION_DEFS:
        perm, _ = Permission.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={"name": name},
        )
        created.append(perm)
    return created


def _collect_app_permissions(app_label, level):
    levels = PERMISSION_LEVELS.get(level, PERMISSION_LEVELS["view"])
    qs = Permission.objects.filter(content_type__app_label=app_label)
    if not levels:
        return Permission.objects.none()
    filters = None
    for action in levels:
        q = Permission.objects.filter(
            content_type__app_label=app_label, codename__startswith=f"{action}_"
        )
        filters = q if filters is None else filters | q
    return filters or qs.none()


def get_permission_groups():
    ensure_custom_permissions()
    groups = []
    for group in PERMISSION_CATEGORIES:
        permissions = []
        app_label = group.get("app_label")
        if app_label:
            permissions = list(
                Permission.objects.filter(content_type__app_label=app_label).order_by(
                    "codename"
                )
            )
        custom = group.get("custom_codenames")
        if custom:
            permissions.extend(
                list(
                    Permission.objects.filter(
                        content_type__app_label="tenants", codename__in=custom
                    ).order_by("codename")
                )
            )
        groups.append(
            {
                "key": group["key"],
                "label": group["label"],
                "permissions": permissions,
            }
        )
    return groups


def get_role_presets(business_type):
    presets = {}
    overrides = BUSINESS_TYPE_OVERRIDES.get(business_type, {})
    for code, base in ROLE_BASE_PRESETS.items():
        data = {
            "name": base.get("name"),
            "description": base.get("description", ""),
            "apps": dict(base.get("apps", {})),
            "custom": list(base.get("custom", [])),
            "extra_permissions": list(base.get("extra_permissions", [])),
        }
        role_override = overrides.get(code)
        if role_override:
            override_apps = role_override.get("apps", {})
            for app_label, level in override_apps.items():
                if level is None:
                    data["apps"].pop(app_label, None)
                else:
                    data["apps"][app_label] = level
            override_custom = role_override.get("custom")
            if override_custom is not None:
                data["custom"] = override_custom
        presets[code] = data
    return presets


def resolve_role_permissions(role_code, business_type):
    ensure_custom_permissions()
    preset = get_role_presets(business_type).get(role_code)
    if not preset:
        return Permission.objects.none()
    if preset.get("apps", {}).get("*") == "full":
        perms = Permission.objects.all()
    else:
        perms = Permission.objects.none()
        for app_label, level in preset.get("apps", {}).items():
            perms = perms | _collect_app_permissions(app_label, level)
    custom = preset.get("custom", [])
    if custom:
        perms = perms | Permission.objects.filter(
            content_type__app_label="tenants", codename__in=custom
        )
    extra = preset.get("extra_permissions", [])
    if extra:
        for perm_key in extra:
            if "." not in perm_key:
                continue
            app_label, codename = perm_key.split(".", 1)
            perms = perms | Permission.objects.filter(
                content_type__app_label=app_label, codename=codename
            )
    return perms.distinct()


def ensure_tenant_roles(business, created_by=None, force=False):
    roles = []
    for code, preset in get_role_presets(business.business_type).items():
        role, created = TenantRole.objects.get_or_create(
            business=business,
            code=code,
            defaults={
                "name": preset["name"],
                "description": preset.get("description", ""),
                "is_system": True,
                "created_by": created_by,
                "updated_by": created_by,
            },
        )
        if created or force:
            role.name = preset["name"]
            role.description = preset.get("description", "")
            role.updated_by = created_by
            role.save(update_fields=["name", "description", "updated_by", "updated_at"])
            role.permissions.set(resolve_role_permissions(code, business.business_type))
        else:
            desired = resolve_role_permissions(code, business.business_type)
            role.permissions.add(*desired.exclude(id__in=role.permissions.values("id")))
        roles.append(role)
    return roles


def permission_key(permission):
    return f"{permission.content_type.app_label}.{permission.codename}"


def reset_role_permissions(role, updated_by=None):
    preset = get_role_presets(role.business.business_type).get(role.code)
    if not preset:
        return role
    role.name = preset["name"]
    role.description = preset.get("description", "")
    role.updated_by = updated_by
    role.save(update_fields=["name", "description", "updated_by", "updated_at"])
    role.permissions.set(resolve_role_permissions(role.code, role.business.business_type))
    return role
