import csv
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import render

from reports.dashboard_handlers import DashboardFactory
from sales.models import Sale
from tenants.decorators import business_required
from tenants.permissions import tenant_permission_required, user_has_tenant_permission
from reports.services import (
    get_cashflow_series,
    get_cashflow_snapshot,
    get_date_range,
    get_gross_margin_summary,
    get_pending_deposits_snapshot,
    get_payment_breakdown,
    get_receivables_aging,
    get_sales_series,
    get_sales_summary,
    get_stock_summary,
)


@login_required
@business_required
def dashboard(request):
    handler = DashboardFactory.get_dashboard(request.business.business_type)
    return handler.render_dashboard(request)


def _export_csv(request, *, filename, headers, rows):
    if not user_has_tenant_permission(request, "reports.export"):
        messages.error(request, "Sem permissao para exportar relatorios.")
        return None
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response


@login_required
@business_required
@tenant_permission_required("reports.view_basic")
def overview(request):
    preset = request.GET.get("preset") or ""
    date_from_raw = request.GET.get("date_from")
    date_to_raw = request.GET.get("date_to")
    if not preset and not date_from_raw and not date_to_raw:
        preset = "30d"
    date_from, date_to = get_date_range(
        date_from=_parse_date(date_from_raw),
        date_to=_parse_date(date_to_raw),
        preset=preset,
        default_days=30,
    )
    summary = get_sales_summary(
        business=request.business, date_from=date_from, date_to=date_to
    )
    period_days = (date_to - date_from).days + 1
    previous_date_to = date_from - timedelta(days=1)
    previous_date_from = previous_date_to - timedelta(days=period_days - 1)
    previous_summary = get_sales_summary(
        business=request.business,
        date_from=previous_date_from,
        date_to=previous_date_to,
    )

    summary_variation = {
        "sales_total": _build_variation(
            current=summary["total"], previous=previous_summary["total"]
        ),
        "transactions": _build_variation(
            current=summary["count"], previous=previous_summary["count"]
        ),
        "ticket": _build_variation(
            current=summary["ticket"], previous=previous_summary["ticket"]
        ),
    }

    gross_margin = get_gross_margin_summary(
        business=request.business, date_from=date_from, date_to=date_to
    )
    cashflow_snapshot = get_cashflow_snapshot(
        business=request.business, date_from=date_from, date_to=date_to
    )
    pending_deposits = get_pending_deposits_snapshot(business=request.business)

    labels, values = get_sales_series(
        business=request.business,
        date_from=date_from,
        date_to=date_to,
        granularity="daily",
    )
    payments = get_payment_breakdown(
        business=request.business, date_from=date_from, date_to=date_to
    )
    payment_labels = [item["label"] for item in payments]
    payment_values = [item["total"] for item in payments]

    context = {
        "date_from": date_from,
        "date_to": date_to,
        "preset": preset,
        "summary": summary,
        "summary_variation": summary_variation,
        "previous_date_from": previous_date_from,
        "previous_date_to": previous_date_to,
        "gross_margin": gross_margin,
        "cashflow_snapshot": cashflow_snapshot,
        "pending_deposits": pending_deposits,
        "sales_labels": labels,
        "sales_values": values,
        "payments": payments,
        "labels": payment_labels,
        "values": payment_values,
    }
    return render(request, "reports/overview.html", context)


@login_required
@business_required
def user_guide(request):
    business = request.business
    tenant_permissions = getattr(request, "tenant_permissions", set())
    is_super = request.user.is_superuser
    is_food_operation = bool(
        business.feature_enabled(business.FEATURE_USE_KITCHEN_DISPLAY)
        and business.feature_enabled(business.FEATURE_USE_RECIPES)
    )
    has_quotations = bool(business.module_quotations_enabled)
    has_cashflow = bool(business.module_cashflow_enabled)
    has_credit = bool(business.allow_credit_sales_enabled)

    setup_steps = [
        {
            "title": "Completar o perfil da empresa",
            "details": "Defina nome comercial, contacto, email oficial, morada, NUIT e logotipo.",
            "menu": "Perfil > Perfil do negocio",
            "url_name": "tenants:business_profile",
        },
        {
            "title": "Configurar regras basicas de operacao",
            "details": "Valide IVA, formato dos documentos, bancos/carteiras e politicas de stock.",
            "menu": "Configuracoes > Configuracoes do sistema",
            "url_name": "tenants:system_settings",
            "visible": is_super or "tenants.manage_tax" in tenant_permissions,
        },
        {
            "title": "Registar catalogo inicial",
            "details": "Crie produtos com preco de venda e custo. Sem preco definido nao ha venda consistente.",
            "menu": "Produtos & Stock",
            "url_name": "catalog:product_list",
            "visible": not is_food_operation,
        },
        {
            "title": "Criar base de clientes",
            "details": "Registe clientes frequentes para historico, credito e documentos fiscais.",
            "menu": "Clientes & Credito",
            "url_name": "customers:list",
            "visible": not is_food_operation,
        },
        {
            "title": "Validar equipa e permissoes",
            "details": "Adicione colaboradores e atribua apenas os acessos necessarios por funcao.",
            "menu": "Configuracoes > Colaboradores / Roles",
            "url_name": "tenants:staff_list",
            "visible": is_super or "tenants.manage_staff" in tenant_permissions,
        },
    ]
    setup_steps = [step for step in setup_steps if step.get("visible", True)]

    menu_reference = [
        {
            "menu": "Dashboard",
            "purpose": "Resumo diario da operacao: vendas, clientes, stock baixo, credito e tendencias.",
            "when": "Primeiro e ultimo ecrã do dia para controlo rapido.",
        },
        {
            "menu": "Operacoes",
            "purpose": "Criar novas vendas/pedidos, acompanhar estado, emitir documentos e gerir excecoes.",
            "when": "Durante atendimento e fecho de vendas.",
        },
        {
            "menu": "Clientes & Credito",
            "purpose": "Registo de clientes, acompanhamento de saldos em aberto e cobrancas.",
            "when": "Sempre que houver vendas a credito ou relacionamento recorrente.",
            "visible": not is_food_operation and has_credit,
        },
        {
            "menu": "Produtos & Stock",
            "purpose": "Registo de produtos, entradas/saidas de stock, inventario e reposicao.",
            "when": "Gestao diaria do armazem e controlo de ruptura.",
            "visible": not is_food_operation,
        },
        {
            "menu": "Faturacao",
            "purpose": "Listar faturas e recibos, reenviar email, imprimir PDF e controlar estado do documento.",
            "when": "Pos-venda e auditoria documental.",
            "visible": not is_food_operation,
        },
        {
            "menu": "Financeiro",
            "purpose": "Fluxo de caixa, despesas, compras e movimentos financeiros por periodo.",
            "when": "Conferencia financeira diaria e mensal.",
            "visible": has_cashflow and not is_food_operation,
        },
        {
            "menu": "Relatorios",
            "purpose": "Analise de desempenho, margem, cashflow, metodos de pagamento e stock.",
            "when": "Tomada de decisao do dono/gestor.",
        },
        {
            "menu": "Perfil",
            "purpose": "Atualizar dados da empresa e do utilizador para documentos e comunicacao.",
            "when": "Sempre que houver mudanca de contacto, morada ou identidade visual.",
        },
        {
            "menu": "Configuracoes",
            "purpose": "Parametrizacao de impostos, equipa, permissoes e politicas operacionais.",
            "when": "Na implementacao inicial e sempre que a operacao evoluir.",
        },
    ]
    menu_reference = [item for item in menu_reference if item.get("visible", True)]

    order_flow = [
        {
            "step": "1. Preparar dados base",
            "action": "Confirme que o produto tem preco e stock, e que o cliente esta registado (se aplicavel).",
            "result": "Evita bloqueios no checkout e documentos incompletos.",
        },
        {
            "step": "2. Criar venda/pedido",
            "action": "Menu Operacoes > Nova venda/Novo pedido. Defina data da operacao, modo e tipo de venda.",
            "result": "Documento fica criado em rascunho para adicionar itens.",
        },
        {
            "step": "3. Adicionar itens e quantidades",
            "action": "Selecione produtos, ajuste quantidade, desconto e impostos conforme politica da empresa.",
            "result": "Total calculado automaticamente com rastreio do stock.",
        },
        {
            "step": "4. Confirmar a venda",
            "action": "Clique em Confirmar para congelar os dados e gerar o fluxo financeiro/documental.",
            "result": "Venda passa para confirmada e entra nos relatorios.",
        },
        {
            "step": "5. Gerar fatura e registar pagamento",
            "action": "Abra a venda e emita a fatura; registe pagamento total ou parcial conforme regra da venda.",
            "result": "Estado de pagamento atualizado e movimentos de caixa registados.",
        },
        {
            "step": "6. Emitir guia de levantamento/entrega",
            "action": "Para levantamento faseado ou deposito, emita guia conforme itens liberados.",
            "result": "Controla o que foi levantado e o que ainda esta pendente.",
        },
        {
            "step": "7. Acompanhar pos-venda",
            "action": "Use Clientes e Relatorios para monitorizar saldo em aberto, margens e performance.",
            "result": "Visibilidade completa da operacao ponta-a-ponta.",
        },
    ]

    quotation_flow = [
        {
            "step": "1. Criar cotacao",
            "action": "Menu Operacoes > Cotacoes > Nova cotacao. Escolha cliente e validade.",
            "result": "Proposta comercial estruturada para aprovacao.",
        },
        {
            "step": "2. Inserir itens da proposta",
            "action": "Adicione produtos, quantidades, preco e desconto negociado.",
            "result": "Valor final da proposta fica pronto para envio.",
        },
        {
            "step": "3. Enviar por email/partilhar PDF",
            "action": "Use o botao de envio para o cliente receber a proposta formal.",
            "result": "Rastreabilidade comercial e comunicacao profissional.",
        },
        {
            "step": "4. Converter em venda",
            "action": "Quando o cliente aprovar, converta para venda para seguir faturacao e entrega.",
            "result": "Evita retrabalho e preserva historico completo.",
        },
    ]

    context = {
        "setup_steps": setup_steps,
        "menu_reference": menu_reference,
        "order_flow": order_flow,
        "quotation_flow": quotation_flow,
        "has_quotations": has_quotations,
        "is_burger": is_food_operation,
    }
    return render(request, "reports/user_guide.html", context)


@login_required
@business_required
@tenant_permission_required("reports.view_basic")
def sales_report(request):
    preset = request.GET.get("preset") or ""
    date_from_raw = request.GET.get("date_from")
    date_to_raw = request.GET.get("date_to")
    granularity = request.GET.get("granularity") or "daily"
    date_from, date_to = get_date_range(
        date_from=_parse_date(date_from_raw),
        date_to=_parse_date(date_to_raw),
        preset=preset,
        default_days=30,
    )
    summary = get_sales_summary(
        business=request.business, date_from=date_from, date_to=date_to
    )
    labels, values = get_sales_series(
        business=request.business,
        date_from=date_from,
        date_to=date_to,
        granularity=granularity,
    )
    table_rows = [{"label": label, "value": value} for label, value in zip(labels, values)]
    period_blocks = _build_sales_period_blocks(
        date_from=date_from,
        date_to=date_to,
        granularity=granularity,
        labels=labels,
        values=values,
    )

    if request.GET.get("export") == "csv":
        rows = []
        for label, value in zip(labels, values):
            rows.append([label, f"{value:.2f}"])
        response = _export_csv(
            request,
            filename="relatorio_vendas.csv",
            headers=["Periodo", "Total"],
            rows=rows,
        )
        if response:
            return response

    context = {
        "date_from": date_from,
        "date_to": date_to,
        "preset": preset,
        "granularity": granularity,
        "summary": summary,
        "labels": labels,
        "values": values,
        "table_rows": table_rows,
        "period_blocks": period_blocks,
    }
    return render(request, "reports/sales.html", context)


def _build_sales_period_blocks(*, date_from, date_to, granularity, labels, values):
    rows = [{"label": label, "value": value} for label, value in zip(labels, values)]
    if granularity != "daily":
        return [{"label": "Períodos", "rows": rows}]

    blocks = []
    current_date = date_from
    for index, value in enumerate(values):
        if current_date > date_to:
            break
        iso = current_date.isocalendar()
        iso_year = int(iso[0])
        iso_week = int(iso[1])
        if not blocks or blocks[-1]["key"] != (iso_year, iso_week):
            blocks.append(
                {
                    "key": (iso_year, iso_week),
                    "week": iso_week,
                    "year": iso_year,
                    "start": current_date,
                    "end": current_date,
                    "rows": [],
                }
            )
        blocks[-1]["rows"].append(
            {
                "label": labels[index] if index < len(labels) else current_date.strftime("%d/%m"),
                "value": value,
            }
        )
        blocks[-1]["end"] = current_date
        current_date += timedelta(days=1)

    return [
        {
            "label": (
                f"Semana {block['week']}/{block['year']} "
                f"({block['start'].strftime('%d/%m')} - {block['end'].strftime('%d/%m')})"
            ),
            "rows": block["rows"],
        }
        for block in blocks
    ]


@login_required
@business_required
@tenant_permission_required("reports.view_finance")
def payment_methods_report(request):
    preset = request.GET.get("preset") or ""
    date_from_raw = request.GET.get("date_from")
    date_to_raw = request.GET.get("date_to")
    date_from, date_to = get_date_range(
        date_from=_parse_date(date_from_raw),
        date_to=_parse_date(date_to_raw),
        preset=preset,
        default_days=30,
    )
    breakdown = get_payment_breakdown(
        business=request.business, date_from=date_from, date_to=date_to
    )

    if request.GET.get("export") == "csv":
        rows = [
            [item["label"], f'{item["total"]:.2f}', item["count"]]
            for item in breakdown
        ]
        response = _export_csv(
            request,
            filename="relatorio_metodos_pagamento.csv",
            headers=["Metodo", "Total", "Transacoes"],
            rows=rows,
        )
        if response:
            return response

    context = {
        "date_from": date_from,
        "date_to": date_to,
        "preset": preset,
        "breakdown": breakdown,
        "labels": [item["label"] for item in breakdown],
        "values": [item["total"] for item in breakdown],
    }
    return render(request, "reports/payments.html", context)


@login_required
@business_required
@tenant_permission_required("reports.view_finance")
def cashflow_report(request):
    preset = request.GET.get("preset") or ""
    date_from_raw = request.GET.get("date_from")
    date_to_raw = request.GET.get("date_to")
    granularity = request.GET.get("granularity") or "daily"
    date_from, date_to = get_date_range(
        date_from=_parse_date(date_from_raw),
        date_to=_parse_date(date_to_raw),
        preset=preset,
        default_days=30,
    )
    labels, values_in, values_out = get_cashflow_series(
        business=request.business,
        date_from=date_from,
        date_to=date_to,
        granularity=granularity,
    )
    total_in = sum(values_in)
    total_out = sum(values_out)

    if request.GET.get("export") == "csv":
        rows = [
            [label, f"{in_value:.2f}", f"{out_value:.2f}"]
            for label, in_value, out_value in zip(labels, values_in, values_out)
        ]
        response = _export_csv(
            request,
            filename="relatorio_fluxo_caixa.csv",
            headers=["Periodo", "Entradas", "Saidas"],
            rows=rows,
        )
        if response:
            return response

    context = {
        "date_from": date_from,
        "date_to": date_to,
        "preset": preset,
        "granularity": granularity,
        "labels": labels,
        "values_in": values_in,
        "values_out": values_out,
        "total_in": total_in,
        "total_out": total_out,
        "net": total_in - total_out,
    }
    return render(request, "reports/cashflow.html", context)


@login_required
@business_required
@tenant_permission_required("reports.view_stock")
def stock_report(request):
    products, low_stock = get_stock_summary(business=request.business)
    total_skus = len(products)
    out_of_stock = sum(1 for item in products if item["quantity"] <= 0)
    total_value = sum(item["stock_value"] for item in products)
    top_value = sorted(products, key=lambda item: item["stock_value"], reverse=True)[:10]

    if request.GET.get("export") == "csv":
        rows = [
            [item["name"], item["quantity"], f'{item["stock_value"]:.2f}']
            for item in products
        ]
        response = _export_csv(
            request,
            filename="relatorio_stock.csv",
            headers=["Produto", "Quantidade", "Valor estimado"],
            rows=rows,
        )
        if response:
            return response

    context = {
        "products": products,
        "low_stock": low_stock,
        "total_skus": total_skus,
        "out_of_stock": out_of_stock,
        "total_value": total_value,
        "labels": [item["name"] for item in top_value],
        "values": [item["stock_value"] for item in top_value],
    }
    return render(request, "reports/stock.html", context)


@login_required
@business_required
@tenant_permission_required("reports.view_finance")
def receivables_report(request):
    buckets, rows = get_receivables_aging(business=request.business)
    if request.GET.get("export") == "csv":
        response = _export_csv(
            request,
            filename="relatorio_recebiveis.csv",
            headers=["Cliente", "Saldo", "Dias em aberto"],
            rows=[
                [row["customer"], f'{row["balance"]:.2f}', row["days"]]
                for row in rows
            ],
        )
        if response:
            return response

    context = {
        "buckets": buckets,
        "rows": rows,
        "labels": list(buckets.keys()),
        "values": list(buckets.values()),
    }
    return render(request, "reports/receivables.html", context)


@login_required
@business_required
@tenant_permission_required("reports.view_basic")
def staff_report(request):
    preset = request.GET.get("preset") or ""
    date_from_raw = request.GET.get("date_from")
    date_to_raw = request.GET.get("date_to")
    date_from, date_to = get_date_range(
        date_from=_parse_date(date_from_raw),
        date_to=_parse_date(date_to_raw),
        preset=preset,
        default_days=30,
    )
    rows = (
        Sale.objects.filter(
            business=request.business,
            status=Sale.STATUS_CONFIRMED,
            sale_date__date__gte=date_from,
            sale_date__date__lte=date_to,
        )
        .values("created_by__first_name", "created_by__last_name", "created_by__username")
        .annotate(
            total=Coalesce(Sum("total"), Decimal("0")),
            count=Coalesce(Count("id"), 0),
        )
        .order_by("-total")
    )
    staff = []
    for row in rows:
        name_parts = [row["created_by__first_name"], row["created_by__last_name"]]
        name = " ".join(part for part in name_parts if part)
        if not name:
            name = row["created_by__username"] or "Sem nome"
        staff.append(
            {
                "name": name,
                "total": float(row["total"]),
                "count": int(row["count"]),
            }
        )

    if request.GET.get("export") == "csv":
        response = _export_csv(
            request,
            filename="relatorio_staff.csv",
            headers=["Colaborador", "Total vendas", "Transacoes"],
            rows=[
                [item["name"], f'{item["total"]:.2f}', item["count"]]
                for item in staff
            ],
        )
        if response:
            return response

    context = {
        "date_from": date_from,
        "date_to": date_to,
        "preset": preset,
        "staff": staff,
        "labels": [item["name"] for item in staff],
        "values": [item["total"] for item in staff],
    }
    return render(request, "reports/staff.html", context)


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _build_variation(*, current, previous):
    current_value = float(current or 0)
    previous_value = float(previous or 0)
    diff = current_value - previous_value
    if previous_value == 0:
        pct = None if current_value == 0 else 100.0
    else:
        pct = (diff / previous_value) * 100
    return {"diff": diff, "pct": pct, "is_positive": diff >= 0}
