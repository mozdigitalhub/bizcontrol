from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from finance.models import CashMovement, FinancialAccount
from food.models import (
    FoodExtra,
    FoodIngredient,
    FoodIngredientCategory,
    FoodIngredientUnit,
    IngredientMovement,
    IngredientStockEntryItem,
    MenuItem,
    MenuItemType,
    MenuItemRecipe,
    Order,
    RestaurantTable,
)
from food.services import (
    create_ingredient_entry,
    create_order,
    ensure_default_ingredient_options,
    ensure_default_menu_options,
    register_order_payment,
    update_order_status,
)
from tenants.models import Business, BusinessMembership


class FoodOrderTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="cook", password="pass")
        self.business = Business.objects.create(name="Burger", slug="burger", business_type=Business.BUSINESS_BURGER)
        BusinessMembership.objects.create(
            business=self.business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        self.menu_item = MenuItem.objects.create(
            business=self.business,
            name="Hamburguer",
            selling_price=Decimal("250.00"),
        )

    def test_create_order_starts_unpaid_for_burger(self):
        order = create_order(
            business=self.business,
            user=self.user,
            order_data={"channel": Order.CHANNEL_DINE_IN, "payment_method": CashMovement.METHOD_CASH},
            items=[{"menu_item": self.menu_item, "quantity": 2, "unit_price": self.menu_item.selling_price}],
        )
        self.assertIsNotNone(order.code)
        self.assertEqual(order.payment_status, Order.PAYMENT_UNPAID)
        self.assertEqual(order.amount_paid, Decimal("0"))
        movement = CashMovement.objects.filter(
            business=self.business, reference_type="order", reference_id=order.id
        ).first()
        self.assertIsNone(movement)

    def test_default_ingredient_options_are_created_for_burger_business(self):
        ensure_default_ingredient_options(self.business)

        categories = set(
            FoodIngredientCategory.objects.filter(business=self.business).values_list(
                "code", flat=True
            )
        )
        units = set(
            FoodIngredientUnit.objects.filter(business=self.business).values_list(
                "code", flat=True
            )
        )

        self.assertIn("meat", categories)
        self.assertIn("bread", categories)
        self.assertIn("grama", units)
        self.assertIn("unidade", units)

    def test_default_menu_options_are_created_for_burger_business(self):
        ensure_default_menu_options(self.business)

        categories = set(
            self.business.menu_categories.values_list("name", flat=True)
        )
        types = set(
            MenuItemType.objects.filter(business=self.business).values_list(
                "code", flat=True
            )
        )

        self.assertIn("Hamburgueres", categories)
        self.assertIn("Bebidas", categories)
        self.assertIn("food", types)
        self.assertIn("complement", types)
        self.assertIn("beverage", types)

    def test_restaurant_table_changes_status_with_order_flow(self):
        business = Business.objects.create(
            name="Restaurante",
            slug="restaurante",
            business_type=Business.BUSINESS_RESTAURANT,
        )
        BusinessMembership.objects.create(
            business=business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        table = RestaurantTable.objects.create(
            business=business,
            name="Mesa 1",
            status=RestaurantTable.STATUS_FREE,
        )
        item = MenuItem.objects.create(
            business=business,
            name="Prato do dia",
            selling_price=Decimal("300.00"),
        )
        order = create_order(
            business=business,
            user=self.user,
            order_data={
                "channel": Order.CHANNEL_DINE_IN,
                "table": table,
                "payment_method": "",
            },
            items=[{"menu_item": item, "quantity": 1, "unit_price": item.selling_price}],
        )
        table.refresh_from_db()
        self.assertEqual(order.table_id, table.id)
        self.assertEqual(table.status, RestaurantTable.STATUS_OCCUPIED)
        register_order_payment(
            order=order,
            business=business,
            user=self.user,
            method=CashMovement.METHOD_CASH,
            amount=order.total,
        )
        update_order_status(order=order, status=Order.STATUS_READY, user=self.user)
        update_order_status(order=order, status=Order.STATUS_DELIVERED, user=self.user)
        table.refresh_from_db()
        self.assertEqual(table.status, RestaurantTable.STATUS_FREE)

    def test_cancel_order_restores_ingredients_and_releases_table(self):
        business = Business.objects.create(
            name="Restaurante B",
            slug="restaurante-b",
            business_type=Business.BUSINESS_RESTAURANT,
        )
        BusinessMembership.objects.create(
            business=business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        table = RestaurantTable.objects.create(
            business=business,
            name="Mesa 2",
            status=RestaurantTable.STATUS_FREE,
        )
        ingredient = FoodIngredient.objects.create(
            business=business,
            name="Queijo",
            stock_qty=Decimal("10.000"),
        )
        menu_item = MenuItem.objects.create(
            business=business,
            name="Prato especial",
            item_type=MenuItem.TYPE_FOOD,
            selling_price=Decimal("450.00"),
        )
        MenuItemRecipe.objects.create(
            menu_item=menu_item,
            ingredient=ingredient,
            quantity=Decimal("2.000"),
            unit="un",
        )

        order = create_order(
            business=business,
            user=self.user,
            order_data={
                "channel": Order.CHANNEL_DINE_IN,
                "table": table,
                "payment_method": "",
            },
            items=[{"menu_item": menu_item, "quantity": 1, "unit_price": menu_item.selling_price}],
        )
        ingredient.refresh_from_db()
        self.assertEqual(ingredient.stock_qty, Decimal("8.000"))

        update_order_status(order=order, status=Order.STATUS_CANCELED, user=self.user)
        ingredient.refresh_from_db()
        table.refresh_from_db()
        self.assertEqual(ingredient.stock_qty, Decimal("10.000"))
        self.assertEqual(table.status, RestaurantTable.STATUS_FREE)
        movement = IngredientMovement.objects.filter(
            business=business,
            ingredient=ingredient,
            movement_type=IngredientMovement.MOVEMENT_CANCEL,
            reference_type="order_cancel",
            reference_id=order.id,
        ).first()
        self.assertIsNotNone(movement)

    def test_order_status_sets_timing_fields(self):
        order = create_order(
            business=self.business,
            user=self.user,
            order_data={
                "channel": Order.CHANNEL_DELIVERY,
                "payment_method": CashMovement.METHOD_CASH,
            },
            items=[{"menu_item": self.menu_item, "quantity": 1, "unit_price": self.menu_item.selling_price}],
        )
        self.assertIsNone(order.preparation_started_at)
        self.assertIsNone(order.ready_at)
        self.assertIsNone(order.delivered_at)

        update_order_status(order=order, status=Order.STATUS_IN_PREPARATION, user=self.user)
        order.refresh_from_db()
        self.assertIsNotNone(order.preparation_started_at)
        self.assertIsNone(order.ready_at)
        self.assertIsNone(order.delivered_at)

        update_order_status(order=order, status=Order.STATUS_READY, user=self.user)
        order.refresh_from_db()
        self.assertIsNotNone(order.ready_at)

        register_order_payment(
            order=order,
            business=self.business,
            user=self.user,
            method=CashMovement.METHOD_CASH,
            amount=order.total,
        )
        update_order_status(order=order, status=Order.STATUS_DELIVERED, user=self.user)
        order.refresh_from_db()
        self.assertIsNotNone(order.delivered_at)

    def test_cannot_deliver_unpaid_order(self):
        order = create_order(
            business=self.business,
            user=self.user,
            order_data={
                "channel": Order.CHANNEL_TAKEAWAY,
                "payment_method": "",
            },
            items=[{"menu_item": self.menu_item, "quantity": 1, "unit_price": self.menu_item.selling_price}],
        )
        update_order_status(order=order, status=Order.STATUS_READY, user=self.user)
        with self.assertRaises(ValidationError):
            update_order_status(order=order, status=Order.STATUS_DELIVERED, user=self.user)

    def test_cannot_change_status_after_cancel(self):
        order = create_order(
            business=self.business,
            user=self.user,
            order_data={
                "channel": Order.CHANNEL_DINE_IN,
                "payment_method": CashMovement.METHOD_CASH,
            },
            items=[{"menu_item": self.menu_item, "quantity": 1, "unit_price": self.menu_item.selling_price}],
        )
        update_order_status(order=order, status=Order.STATUS_CANCELED, user=self.user)
        with self.assertRaises(ValidationError):
            update_order_status(order=order, status=Order.STATUS_DELIVERED, user=self.user)

    def test_cannot_skip_from_confirmed_to_delivered_even_when_paid(self):
        order = create_order(
            business=self.business,
            user=self.user,
            order_data={
                "channel": Order.CHANNEL_TAKEAWAY,
                "payment_method": "",
            },
            items=[{"menu_item": self.menu_item, "quantity": 1, "unit_price": self.menu_item.selling_price}],
        )
        register_order_payment(
            order=order,
            business=self.business,
            user=self.user,
            method=CashMovement.METHOD_CASH,
            amount=order.total,
        )
        with self.assertRaises(ValidationError):
            update_order_status(order=order, status=Order.STATUS_DELIVERED, user=self.user)

    def test_register_order_payment_links_cash_movement_to_payment(self):
        order = create_order(
            business=self.business,
            user=self.user,
            order_data={
                "channel": Order.CHANNEL_DINE_IN,
                "payment_method": "",
            },
            items=[{"menu_item": self.menu_item, "quantity": 1, "unit_price": self.menu_item.selling_price}],
        )
        _, payment = register_order_payment(
            order=order,
            business=self.business,
            user=self.user,
            method=CashMovement.METHOD_CASH,
            amount=Decimal("100.00"),
        )
        movement = CashMovement.objects.filter(
            business=self.business,
            reference_type="order_payment",
            reference_id=payment.id,
        ).first()
        self.assertIsNotNone(movement)
        self.assertIn(str(payment.id), movement.notes)

    def test_ingredient_entry_converts_purchase_unit_to_base_unit(self):
        ingredient = FoodIngredient.objects.create(
            business=self.business,
            name="Ovo",
            category=FoodIngredient.CATEGORY_EXTRA,
            unit="unidade",
            stock_qty=Decimal("8.000"),
            reorder_level=Decimal("20.000"),
        )

        entry = create_ingredient_entry(
            business=self.business,
            user=self.user,
            entry_data={
                "supplier_name": "Fornecedor A",
                "reference_number": "OV-1",
                "entry_date": date(2026, 4, 24),
                "notes": "",
            },
            items=[
                {
                    "ingredient": ingredient,
                    "purchased_quantity": Decimal("2"),
                    "purchase_unit": "caixa",
                    "conversion_factor": Decimal("30"),
                    "total_cost": Decimal("300.00"),
                }
            ],
        )

        ingredient.refresh_from_db()
        self.assertEqual(ingredient.stock_qty, Decimal("68.000"))
        self.assertEqual(ingredient.cost_price, Decimal("5.00"))

        item = IngredientStockEntryItem.objects.get(entry=entry)
        self.assertEqual(item.quantity, Decimal("60"))
        self.assertEqual(item.unit_cost, Decimal("5.00"))
        movement = IngredientMovement.objects.get(
            business=self.business,
            ingredient=ingredient,
            movement_type=IngredientMovement.MOVEMENT_IN,
            reference_type="ingredient_entry",
            reference_id=entry.id,
        )
        self.assertEqual(movement.quantity, Decimal("60.000"))
        self.assertEqual(movement.unit, "unidade")

    def test_order_deducts_recipe_in_base_units(self):
        meat = FoodIngredient.objects.create(
            business=self.business,
            name="Carne",
            category=FoodIngredient.CATEGORY_MEAT,
            unit="grama",
            stock_qty=Decimal("1000.000"),
        )
        cheese = FoodIngredient.objects.create(
            business=self.business,
            name="Queijo",
            category=FoodIngredient.CATEGORY_DAIRY,
            unit="fatia",
            stock_qty=Decimal("20.000"),
        )
        burger = MenuItem.objects.create(
            business=self.business,
            name="Burger Especial",
            item_type=MenuItem.TYPE_FOOD,
            selling_price=Decimal("350.00"),
        )
        MenuItemRecipe.objects.create(
            menu_item=burger,
            ingredient=meat,
            quantity=Decimal("150.000"),
            unit="grama",
        )
        MenuItemRecipe.objects.create(
            menu_item=burger,
            ingredient=cheese,
            quantity=Decimal("2.000"),
            unit="fatia",
        )

        order = create_order(
            business=self.business,
            user=self.user,
            order_data={
                "channel": Order.CHANNEL_DINE_IN,
                "payment_method": CashMovement.METHOD_CASH,
            },
            items=[
                {"menu_item": burger, "quantity": 3, "unit_price": burger.selling_price}
            ],
        )

        meat.refresh_from_db()
        cheese.refresh_from_db()
        self.assertEqual(meat.stock_qty, Decimal("550.000"))
        self.assertEqual(cheese.stock_qty, Decimal("14.000"))
        self.assertEqual(
            IngredientMovement.objects.filter(
                business=self.business,
                reference_type="order",
                reference_id=order.id,
                movement_type=IngredientMovement.MOVEMENT_OUT,
            ).count(),
            2,
        )

    def test_order_deducts_linked_complement_stock(self):
        fries = FoodIngredient.objects.create(
            business=self.business,
            name="Batata frita",
            category=FoodIngredient.CATEGORY_EXTRA,
            usage_type=FoodIngredient.USAGE_SELLABLE,
            unit="unidade",
            stock_qty=Decimal("10.000"),
        )
        combo = MenuItem.objects.create(
            business=self.business,
            name="Burger com batata",
            item_type=MenuItem.TYPE_FOOD,
            selling_price=Decimal("350.00"),
        )
        extra = FoodExtra.objects.create(
            business=self.business,
            name="Dose de batatas",
            extra_type=FoodExtra.TYPE_EXTRA,
            extra_price=Decimal("80.00"),
            ingredient=fries,
        )

        order = create_order(
            business=self.business,
            user=self.user,
            order_data={
                "channel": Order.CHANNEL_DINE_IN,
                "payment_method": CashMovement.METHOD_CASH,
            },
            items=[
                {
                    "menu_item": combo,
                    "quantity": 2,
                    "unit_price": combo.selling_price,
                    "extras": [extra],
                }
            ],
        )

        fries.refresh_from_db()
        self.assertEqual(fries.stock_qty, Decimal("8.000"))
        self.assertTrue(
            IngredientMovement.objects.filter(
                business=self.business,
                ingredient=fries,
                reference_type="order",
                reference_id=order.id,
                movement_type=IngredientMovement.MOVEMENT_OUT,
            ).exists()
        )

    def test_cancel_after_preparation_does_not_restore_ingredients(self):
        ingredient = FoodIngredient.objects.create(
            business=self.business,
            name="Pao",
            category=FoodIngredient.CATEGORY_BREAD,
            unit="unidade",
            stock_qty=Decimal("10.000"),
        )
        burger = MenuItem.objects.create(
            business=self.business,
            name="Burger com pao",
            item_type=MenuItem.TYPE_FOOD,
            selling_price=Decimal("250.00"),
        )
        MenuItemRecipe.objects.create(
            menu_item=burger,
            ingredient=ingredient,
            quantity=Decimal("1.000"),
            unit="unidade",
        )
        order = create_order(
            business=self.business,
            user=self.user,
            order_data={
                "channel": Order.CHANNEL_DINE_IN,
                "payment_method": CashMovement.METHOD_CASH,
            },
            items=[
                {"menu_item": burger, "quantity": 2, "unit_price": burger.selling_price}
            ],
        )
        update_order_status(order=order, status=Order.STATUS_IN_PREPARATION, user=self.user)
        order.refresh_from_db()
        update_order_status(order=order, status=Order.STATUS_CANCELED, user=self.user)

        ingredient.refresh_from_db()
        self.assertEqual(ingredient.stock_qty, Decimal("8.000"))
        self.assertFalse(
            IngredientMovement.objects.filter(
                business=self.business,
                ingredient=ingredient,
                movement_type=IngredientMovement.MOVEMENT_CANCEL,
                reference_id=order.id,
            ).exists()
        )


class FoodCashflowDashboardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="cash-admin",
            email="cash-admin@example.com",
            password="pass1234",
        )
        self.business = Business.objects.create(
            name="Burger Flow",
            slug="burger-flow",
            business_type=Business.BUSINESS_BURGER,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.user,
            role=BusinessMembership.ROLE_OWNER,
        )
        self.account = FinancialAccount.objects.create(
            business=self.business,
            name="Caixa Teste Burger",
            category=FinancialAccount.CATEGORY_CASH,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["business_id"] = self.business.id
        session.save()

    def test_cashflow_dashboard_renders_for_burger_business(self):
        CashMovement.objects.create(
            business=self.business,
            account=self.account,
            category=self.account.category,
            movement_type=CashMovement.MOVEMENT_IN,
            amount=Decimal("1200.00"),
            method=CashMovement.METHOD_CASH,
            reference_type="burger_manual",
            happened_at=timezone.now(),
            created_by=self.user,
        )
        response = self.client.get(reverse("food:cashflow_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "food/cashflow_dashboard.html")
        self.assertContains(response, "Fluxo de caixa da hamburgueria")

    def test_cashflow_dashboard_registers_manual_movement(self):
        response = self.client.post(
            reverse("food:cashflow_dashboard"),
            {
                "action": "add_movement",
                "movement_type": CashMovement.MOVEMENT_OUT,
                "amount": "450.00",
                "method": CashMovement.METHOD_CASH,
                "account": str(self.account.id),
                "reference_type": "burger_manual",
                "happened_on": "2026-04-24",
                "notes": "Compra de gás",
            },
        )
        self.assertEqual(response.status_code, 302)
        movement = CashMovement.objects.filter(
            business=self.business,
            reference_type="burger_manual",
            notes="Compra de gás",
        ).first()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.account_id, self.account.id)
        self.assertEqual(movement.amount, Decimal("450.00"))
        self.assertEqual(movement.movement_type, CashMovement.MOVEMENT_OUT)

    def test_cashflow_dashboard_redirects_when_business_is_not_burger(self):
        hardware = Business.objects.create(
            name="Ferragem",
            slug="ferragem-flow",
            business_type=Business.BUSINESS_HARDWARE,
        )
        session = self.client.session
        session["business_id"] = hardware.id
        session.save()
        response = self.client.get(reverse("food:cashflow_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("reports:dashboard"), response.url)


class FoodOrderPaymentModalTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="cashier",
            email="cashier@example.com",
            password="pass1234",
        )
        self.business = Business.objects.create(
            name="Burger Modal",
            slug="burger-modal",
            business_type=Business.BUSINESS_BURGER,
        )
        BusinessMembership.objects.create(
            business=self.business, user=self.user, role=BusinessMembership.ROLE_OWNER
        )
        self.item = MenuItem.objects.create(
            business=self.business,
            name="Burger Simples",
            selling_price=Decimal("180.00"),
        )
        self.order = create_order(
            business=self.business,
            user=self.user,
            order_data={"channel": Order.CHANNEL_TAKEAWAY, "payment_method": ""},
            items=[{"menu_item": self.item, "quantity": 1, "unit_price": self.item.selling_price}],
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["business_id"] = self.business.id
        session.save()

    def test_payment_modal_get(self):
        response = self.client.get(
            reverse("food:order_payment_modal", args=[self.order.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirmar pagamento")

    def test_payment_modal_post_ajax_registers_payment(self):
        response = self.client.post(
            reverse("food:order_payment_modal", args=[self.order.id]),
            {
                "method": CashMovement.METHOD_CASH,
                "amount": "180.00",
                "next": reverse("food:order_list"),
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content.decode("utf-8"),
            {"ok": True, "redirect_url": reverse("food:order_list")},
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PAYMENT_PAID)


class FoodFinancialPermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_superuser(
            username="owner-finance",
            email="owner-finance@example.com",
            password="pass1234",
        )
        self.viewer = User.objects.create_user(
            username="viewer-finance",
            password="pass1234",
        )
        view_order_perm = Permission.objects.get(codename="view_order")
        self.viewer.user_permissions.add(view_order_perm)

        self.business = Business.objects.create(
            name="Burger Secure",
            slug="burger-secure",
            business_type=Business.BUSINESS_BURGER,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.owner,
            role=BusinessMembership.ROLE_OWNER,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.viewer,
            role=BusinessMembership.ROLE_STAFF,
        )
        self.item = MenuItem.objects.create(
            business=self.business,
            name="Burger Base",
            selling_price=Decimal("150.00"),
        )
        self.order = create_order(
            business=self.business,
            user=self.owner,
            order_data={"channel": Order.CHANNEL_TAKEAWAY, "payment_method": ""},
            items=[{"menu_item": self.item, "quantity": 1, "unit_price": self.item.selling_price}],
        )

    def _login_with_business(self, user):
        self.client.force_login(user)
        session = self.client.session
        session["business_id"] = self.business.id
        session.save()

    def test_view_only_user_cannot_open_payment_modal(self):
        self._login_with_business(self.viewer)
        response = self.client.get(reverse("food:order_payment_modal", args=[self.order.id]))
        self.assertEqual(response.status_code, 403)

    def test_view_only_user_cannot_post_payment_on_checkout(self):
        self._login_with_business(self.viewer)
        response = self.client.post(
            reverse("food:order_checkout", args=[self.order.id]),
            {
                "method": CashMovement.METHOD_CASH,
                "amount": "150.00",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_view_only_user_cannot_open_cashflow_dashboard(self):
        self._login_with_business(self.viewer)
        response = self.client.get(reverse("food:cashflow_dashboard"))
        self.assertEqual(response.status_code, 403)


class FoodOrderCreateBurgerFlowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="burger-order-admin",
            email="burger-order-admin@example.com",
            password="pass1234",
        )
        self.business = Business.objects.create(
            name="Burger UI",
            slug="burger-ui",
            business_type=Business.BUSINESS_BURGER,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.user,
            role=BusinessMembership.ROLE_OWNER,
        )
        ensure_default_menu_options(self.business)
        self.dish = MenuItem.objects.create(
            business=self.business,
            name="Burger Classico",
            item_type=MenuItem.TYPE_FOOD,
            selling_price=Decimal("250.00"),
        )
        self.complement = MenuItem.objects.create(
            business=self.business,
            name="Dose de batatas",
            item_type=MenuItem.TYPE_COMPLEMENT,
            selling_price=Decimal("90.00"),
        )
        drink_stock = FoodIngredient.objects.create(
            business=self.business,
            name="Refresco lata",
            usage_type=FoodIngredient.USAGE_SELLABLE,
            unit="unidade",
            stock_qty=Decimal("100.000"),
        )
        self.beverage = MenuItem.objects.create(
            business=self.business,
            name="Refresco",
            item_type=MenuItem.TYPE_BEVERAGE,
            selling_price=Decimal("70.00"),
            ingredient=drink_stock,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["business_id"] = self.business.id
        session.save()

    def test_order_form_separates_dishes_complements_and_beverages(self):
        response = self.client.get(reverse("food:order_create"))
        self.assertEqual(response.status_code, 200)
        form = response.context["formset"].forms[0]
        menu_ids = set(form.fields["menu_item"].queryset.values_list("id", flat=True))
        self.assertEqual(menu_ids, {self.dish.id})
        self.assertIn(self.complement, form.fields["complements"].queryset)
        self.assertIn(self.beverage, form.fields["beverages"].queryset)

    def test_order_create_expands_selected_complements_and_beverages(self):
        response = self.client.post(
            reverse("food:order_create"),
            {
                "customer": "",
                "channel": Order.CHANNEL_TAKEAWAY,
                "table": "",
                "notes": "",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-menu_item": str(self.dish.id),
                "items-0-quantity": "2",
                "items-0-unit_price": "",
                "items-0-notes": "",
                "items-0-complements": [str(self.complement.id)],
                "items-0-beverages": [str(self.beverage.id)],
                "items-0-DELETE": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        order = Order.objects.filter(business=self.business).latest("id")
        self.assertEqual(order.items.count(), 3)
        self.assertEqual(
            order.items.filter(menu_item=self.dish).values_list("quantity", flat=True).first(),
            2,
        )
        self.assertEqual(
            order.items.filter(menu_item=self.complement).values_list("quantity", flat=True).first(),
            2,
        )
        self.assertEqual(
            order.items.filter(menu_item=self.beverage).values_list("quantity", flat=True).first(),
            2,
        )
        expected_total = (self.dish.selling_price + self.complement.selling_price + self.beverage.selling_price) * 2
        self.assertEqual(order.total, expected_total)
