from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from catalog.models import Category, Product
from tenants.models import Business


PRODUCTS = [
    {
        "name": "Cimento Nacional 32",
        "sku": "CIM-32",
        "category": "Cimento",
        "unit": "saco",
        "cost": Decimal("320"),
        "price": Decimal("450"),
        "reorder": Decimal("20"),
    },
    {
        "name": "Cimento Nacional 42",
        "sku": "CIM-42",
        "category": "Cimento",
        "unit": "saco",
        "cost": Decimal("360"),
        "price": Decimal("520"),
        "reorder": Decimal("20"),
    },
    {
        "name": "Ferro 8mm",
        "sku": "FER-08",
        "category": "Ferro e Arame",
        "unit": "metro",
        "cost": Decimal("85"),
        "price": Decimal("120"),
        "reorder": Decimal("100"),
    },
    {
        "name": "Ferro 10mm",
        "sku": "FER-10",
        "category": "Ferro e Arame",
        "unit": "metro",
        "cost": Decimal("110"),
        "price": Decimal("150"),
        "reorder": Decimal("80"),
    },
    {
        "name": "Ferro 12mm",
        "sku": "FER-12",
        "category": "Ferro e Arame",
        "unit": "metro",
        "cost": Decimal("135"),
        "price": Decimal("180"),
        "reorder": Decimal("80"),
    },
    {
        "name": "Arame recozido",
        "sku": "ARA-REC",
        "category": "Ferro e Arame",
        "unit": "kg",
        "cost": Decimal("110"),
        "price": Decimal("160"),
        "reorder": Decimal("50"),
    },
    {
        "name": "Areia lavada",
        "sku": "ARE-LAV",
        "category": "Agregados",
        "unit": "saco",
        "cost": Decimal("80"),
        "price": Decimal("130"),
        "reorder": Decimal("30"),
    },
    {
        "name": "Pedra brita",
        "sku": "PED-BRI",
        "category": "Agregados",
        "unit": "saco",
        "cost": Decimal("90"),
        "price": Decimal("140"),
        "reorder": Decimal("25"),
    },
    {
        "name": "Bloco 15",
        "sku": "BLO-15",
        "category": "Blocos e Tijolos",
        "unit": "un",
        "cost": Decimal("18"),
        "price": Decimal("30"),
        "reorder": Decimal("200"),
    },
    {
        "name": "Bloco 20",
        "sku": "BLO-20",
        "category": "Blocos e Tijolos",
        "unit": "un",
        "cost": Decimal("22"),
        "price": Decimal("35"),
        "reorder": Decimal("180"),
    },
    {
        "name": "Tijolo comum",
        "sku": "TIJ-COM",
        "category": "Blocos e Tijolos",
        "unit": "un",
        "cost": Decimal("4"),
        "price": Decimal("8"),
        "reorder": Decimal("500"),
    },
    {
        "name": "Tinta esmalte 3.6L",
        "sku": "TIN-ESM-36",
        "category": "Tintas e Pintura",
        "unit": "litro",
        "cost": Decimal("480"),
        "price": Decimal("650"),
        "reorder": Decimal("10"),
    },
    {
        "name": "Tinta PVA 18L",
        "sku": "TIN-PVA-18",
        "category": "Tintas e Pintura",
        "unit": "litro",
        "cost": Decimal("1100"),
        "price": Decimal("1450"),
        "reorder": Decimal("6"),
    },
    {
        "name": "Cola branca 1L",
        "sku": "COL-01",
        "category": "Colas e Vedantes",
        "unit": "litro",
        "cost": Decimal("120"),
        "price": Decimal("180"),
        "reorder": Decimal("15"),
    },
    {
        "name": "Silicone 280ml",
        "sku": "SIL-280",
        "category": "Colas e Vedantes",
        "unit": "un",
        "cost": Decimal("90"),
        "price": Decimal("140"),
        "reorder": Decimal("30"),
    },
    {
        "name": "Prego 2 polegadas",
        "sku": "PRE-02",
        "category": "Fixacao",
        "unit": "pacote",
        "cost": Decimal("60"),
        "price": Decimal("95"),
        "reorder": Decimal("20"),
    },
    {
        "name": "Prego 3 polegadas",
        "sku": "PRE-03",
        "category": "Fixacao",
        "unit": "pacote",
        "cost": Decimal("70"),
        "price": Decimal("110"),
        "reorder": Decimal("20"),
    },
    {
        "name": "Parafuso 6x50",
        "sku": "PAR-6X50",
        "category": "Fixacao",
        "unit": "caixa",
        "cost": Decimal("180"),
        "price": Decimal("260"),
        "reorder": Decimal("10"),
    },
    {
        "name": "Parafuso 8x60",
        "sku": "PAR-8X60",
        "category": "Fixacao",
        "unit": "caixa",
        "cost": Decimal("210"),
        "price": Decimal("300"),
        "reorder": Decimal("10"),
    },
    {
        "name": "Bucha 6mm",
        "sku": "BUC-06",
        "category": "Fixacao",
        "unit": "pacote",
        "cost": Decimal("40"),
        "price": Decimal("65"),
        "reorder": Decimal("25"),
    },
    {
        "name": "Bucha 8mm",
        "sku": "BUC-08",
        "category": "Fixacao",
        "unit": "pacote",
        "cost": Decimal("45"),
        "price": Decimal("70"),
        "reorder": Decimal("25"),
    },
    {
        "name": "Fita teflon",
        "sku": "FIT-TEF",
        "category": "Canalizacao",
        "unit": "un",
        "cost": Decimal("15"),
        "price": Decimal("25"),
        "reorder": Decimal("40"),
    },
    {
        "name": "Cabo eletrico 2.5mm",
        "sku": "CAB-25",
        "category": "Eletricidade",
        "unit": "metro",
        "cost": Decimal("45"),
        "price": Decimal("70"),
        "reorder": Decimal("200"),
    },
    {
        "name": "Cabo eletrico 1.5mm",
        "sku": "CAB-15",
        "category": "Eletricidade",
        "unit": "metro",
        "cost": Decimal("30"),
        "price": Decimal("50"),
        "reorder": Decimal("200"),
    },
    {
        "name": "Tubo PVC 20mm",
        "sku": "PVC-20",
        "category": "Canalizacao",
        "unit": "metro",
        "cost": Decimal("60"),
        "price": Decimal("95"),
        "reorder": Decimal("50"),
    },
    {
        "name": "Joelho PVC 20mm",
        "sku": "PVC-J20",
        "category": "Canalizacao",
        "unit": "un",
        "cost": Decimal("20"),
        "price": Decimal("35"),
        "reorder": Decimal("40"),
    },
    {
        "name": "Tomada simples",
        "sku": "TOM-01",
        "category": "Eletricidade",
        "unit": "un",
        "cost": Decimal("60"),
        "price": Decimal("95"),
        "reorder": Decimal("30"),
    },
    {
        "name": "Interruptor simples",
        "sku": "INT-01",
        "category": "Eletricidade",
        "unit": "un",
        "cost": Decimal("55"),
        "price": Decimal("90"),
        "reorder": Decimal("30"),
    },
    {
        "name": "Ladrilho ceramica 30x30",
        "sku": "LAD-3030",
        "category": "Revestimentos",
        "unit": "caixa",
        "cost": Decimal("750"),
        "price": Decimal("980"),
        "reorder": Decimal("8"),
    },
    {
        "name": "Cimento cola 20kg",
        "sku": "CIM-COL20",
        "category": "Cimento",
        "unit": "saco",
        "cost": Decimal("210"),
        "price": Decimal("320"),
        "reorder": Decimal("15"),
    },
]


class Command(BaseCommand):
    help = "Cria 30 produtos mais vendidos para uma ferragem e associa a uma categoria."

    def add_arguments(self, parser):
        parser.add_argument("--business-id", type=int, help="ID do negocio")
        parser.add_argument("--business-slug", type=str, help="Slug do negocio")

    def handle(self, *args, **options):
        business = self._resolve_business(options)
        if business.business_type != Business.BUSINESS_HARDWARE:
            raise CommandError("O negocio indicado nao e do tipo ferragem.")

        categories = {}
        created_categories = 0
        for item in PRODUCTS:
            cat_name = item["category"]
            if cat_name not in categories:
                category, was_created = Category.objects.get_or_create(
                    business=business, name=cat_name, defaults={"is_active": True}
                )
                categories[cat_name] = category
                if was_created:
                    created_categories += 1

        created = 0
        updated = 0
        for item in PRODUCTS:
            defaults = {
                "sku": item["sku"],
                "category": categories.get(item["category"]),
                "unit_of_measure": item["unit"],
                "stock_control_mode": Product.STOCK_AUTOMATIC,
                "cost_price": item["cost"],
                "sale_price": item["price"],
                "reorder_level": item["reorder"],
                "is_active": True,
            }
            product, was_created = Product.objects.get_or_create(
                business=business, name=item["name"], defaults=defaults
            )
            if was_created:
                created += 1
            else:
                changed = False
                for field, value in defaults.items():
                    if getattr(product, field) != value:
                        setattr(product, field, value)
                        changed = True
                if changed:
                    product.save()
                    updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Produtos criados: "
                f"{created}. Atualizados: {updated}. "
                f"Categorias novas: {created_categories}. "
                f"Categorias totais: {len(categories)}"
            )
        )
        self.stdout.write("Categorias usadas:")
        for name in sorted(categories.keys()):
            count = sum(1 for item in PRODUCTS if item["category"] == name)
            self.stdout.write(f"- {name} ({count} produtos)")

    def _resolve_business(self, options):
        business_id = options.get("business_id")
        business_slug = options.get("business_slug")
        if business_id:
            return Business.objects.get(id=business_id)
        if business_slug:
            return Business.objects.get(slug=business_slug)
        qs = Business.objects.filter(business_type=Business.BUSINESS_HARDWARE)
        count = qs.count()
        if count == 1:
            return qs.first()
        if count == 0:
            raise CommandError("Nenhum negocio do tipo ferragem encontrado.")
        raise CommandError(
            "Existe mais de um negocio do tipo ferragem. Use --business-id ou --business-slug."
        )
