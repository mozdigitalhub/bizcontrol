from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardModule:
    key: str
    title: str
    description: str
    url_name: str
    permission: str = ""


@dataclass(frozen=True)
class DashboardNavigationProfile:
    use_food_operations: bool = False
    show_customer_credit: bool = True
    show_billing: bool = True
    show_finance: bool = True
    show_food_tables: bool = False
    products_section_title: str = "Produtos & Stock"
