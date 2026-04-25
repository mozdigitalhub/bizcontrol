from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.text import slugify

from catalog.models import Product
from customers.models import Customer
from tenants.models import Business


class RestaurantTable(models.Model):
    STATUS_FREE = "free"
    STATUS_OCCUPIED = "occupied"
    STATUS_RESERVED = "reserved"
    STATUS_CHOICES = [
        (STATUS_FREE, "Livre"),
        (STATUS_OCCUPIED, "Ocupada"),
        (STATUS_RESERVED, "Reservada"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="restaurant_tables"
    )
    name = models.CharField(max_length=60)
    seats = models.PositiveIntegerField(default=4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_FREE)
    reserved_for = models.CharField(max_length=120, blank=True)
    reserved_until = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "name"],
                name="uniq_restaurant_table_name_business",
            )
        ]
        indexes = [
            models.Index(fields=["business", "status"]),
        ]

    def __str__(self):
        return self.name


class Order(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_CONFIRMED = "confirmed"
    STATUS_IN_PREPARATION = "in_preparation"
    STATUS_READY = "ready"
    STATUS_DELIVERED = "delivered"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Rascunho"),
        (STATUS_CONFIRMED, "Confirmado"),
        (STATUS_IN_PREPARATION, "Em preparacao"),
        (STATUS_READY, "Pronto"),
        (STATUS_DELIVERED, "Entregue"),
        (STATUS_CANCELED, "Cancelado"),
    ]

    CHANNEL_DINE_IN = "dine_in"
    CHANNEL_TAKEAWAY = "take_away"
    CHANNEL_DELIVERY = "delivery"
    CHANNEL_CHOICES = [
        (CHANNEL_DINE_IN, "Mesa"),
        (CHANNEL_TAKEAWAY, "Take away"),
        (CHANNEL_DELIVERY, "Delivery"),
    ]

    PAYMENT_UNPAID = "unpaid"
    PAYMENT_PARTIAL = "partial"
    PAYMENT_PAID = "paid"
    PAYMENT_CHOICES = [
        (PAYMENT_UNPAID, "Nao pago"),
        (PAYMENT_PARTIAL, "Parcial"),
        (PAYMENT_PAID, "Pago"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="food_orders"
    )
    table = models.ForeignKey(
        RestaurantTable,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    code = models.CharField(max_length=30, null=True, blank=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_DINE_IN)
    payment_method = models.CharField(max_length=20, blank=True)
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_CHOICES, default=PAYMENT_UNPAID
    )
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    preparation_started_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_food_orders",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_food_orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "code"],
                condition=Q(code__isnull=False),
                name="uniq_food_order_code_business",
            )
        ]
        indexes = [
            models.Index(fields=["business", "created_at"]),
            models.Index(fields=["business", "status"]),
        ]

    def __str__(self):
        return self.code or f"Pedido {self.id}"


class MenuCategory(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="menu_categories"
    )
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("business", "name")
        indexes = [
            models.Index(fields=["business", "name"]),
        ]

    def __str__(self):
        return self.name


class MenuItemType(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="menu_item_types"
    )
    name = models.CharField(max_length=80)
    code = models.SlugField(max_length=30)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "code"],
                name="uniq_menu_item_type_business_code",
            )
        ]
        indexes = [
            models.Index(fields=["business", "name"]),
        ]

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name)[:30] or "tipo"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    TYPE_FOOD = "food"
    TYPE_COMPLEMENT = "complement"
    TYPE_BEVERAGE = "beverage"
    TYPE_CHOICES = [
        (TYPE_FOOD, "Prato"),
        (TYPE_COMPLEMENT, "Complemento"),
        (TYPE_BEVERAGE, "Bebida"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="menu_items"
    )
    category = models.ForeignKey(
        MenuCategory, on_delete=models.SET_NULL, null=True, blank=True
    )
    name = models.CharField(max_length=160)
    description = models.CharField(max_length=255, blank=True)
    item_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_FOOD)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    image = models.ImageField(upload_to="menu_items/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    ingredient = models.ForeignKey(
        "FoodIngredient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beverage_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("business", "name")
        indexes = [
            models.Index(fields=["business", "name"]),
            models.Index(fields=["business", "item_type"]),
        ]

    def __str__(self):
        return self.name


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    line_tax = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.CharField(max_length=255, blank=True)

    def __str__(self):
        label = self.menu_item or self.product or "-"
        return f"{label} x {self.quantity}"


class FoodExtra(models.Model):
    TYPE_EXTRA = "extra"
    TYPE_VARIANT = "variant"
    TYPE_CHOICES = [
        (TYPE_EXTRA, "Complemento"),
        (TYPE_VARIANT, "Bebida adicional"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="food_extras"
    )
    name = models.CharField(max_length=120)
    extra_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_EXTRA)
    extra_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ingredient = models.ForeignKey(
        "FoodIngredient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="food_complements",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "extra_type"]),
        ]

    def __str__(self):
        return self.name


class OrderItemExtra(models.Model):
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name="extras"
    )
    extra = models.ForeignKey(FoodExtra, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.extra} x {self.quantity}"


class OrderPayment(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="payments"
    )
    method = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="food_payments",
    )

    def __str__(self):
        return f"{self.order_id} - {self.amount}"


class FoodIngredientCategory(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="food_ingredient_categories"
    )
    name = models.CharField(max_length=80)
    code = models.SlugField(max_length=30)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "code"],
                name="uniq_food_ingredient_category_business_code",
            )
        ]
        indexes = [
            models.Index(fields=["business", "name"]),
        ]

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name)[:30] or "categoria"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class FoodIngredientUnit(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="food_ingredient_units"
    )
    name = models.CharField(max_length=80)
    code = models.SlugField(max_length=20)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "code"],
                name="uniq_food_ingredient_unit_business_code",
            )
        ]
        indexes = [
            models.Index(fields=["business", "name"]),
        ]

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name)[:20] or "unidade"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class FoodIngredient(models.Model):
    USAGE_RECIPE = "recipe"
    USAGE_SELLABLE = "sellable"
    USAGE_BOTH = "both"
    USAGE_CHOICES = [
        (USAGE_RECIPE, "Composicao de pratos"),
        (USAGE_SELLABLE, "Produto vendavel"),
        (USAGE_BOTH, "Composicao e venda"),
    ]

    CATEGORY_MEAT = "meat"
    CATEGORY_BREAD = "bread"
    CATEGORY_DAIRY = "dairy"
    CATEGORY_BEVERAGE = "beverage"
    CATEGORY_SAUCE = "sauce"
    CATEGORY_PACKAGING = "packaging"
    CATEGORY_EXTRA = "extra"
    CATEGORY_CONDIMENT = "condiment"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_MEAT, "Carnes"),
        (CATEGORY_BREAD, "Paes"),
        (CATEGORY_DAIRY, "Laticinios"),
        (CATEGORY_BEVERAGE, "Bebidas"),
        (CATEGORY_SAUCE, "Molhos"),
        (CATEGORY_PACKAGING, "Embalagens"),
        (CATEGORY_EXTRA, "Extras"),
        (CATEGORY_CONDIMENT, "Condimentos"),
        (CATEGORY_OTHER, "Outros"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="food_ingredients"
    )
    name = models.CharField(max_length=120)
    category = models.CharField(
        max_length=30, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER
    )
    usage_type = models.CharField(
        max_length=20, choices=USAGE_CHOICES, default=USAGE_RECIPE
    )
    unit = models.CharField(max_length=20, blank=True)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    stock_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    stock_control = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("business", "name")
        indexes = [
            models.Index(fields=["business", "name"]),
            models.Index(fields=["business", "category"]),
        ]

    def __str__(self):
        return self.name


class MenuItemRecipe(models.Model):
    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.CASCADE, related_name="recipes"
    )
    ingredient = models.ForeignKey(
        FoodIngredient, on_delete=models.CASCADE, related_name="recipes"
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=20, blank=True)

    class Meta:
        unique_together = ("menu_item", "ingredient")

    def __str__(self):
        return f"{self.menu_item} - {self.ingredient}"


class IngredientStockEntry(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="ingredient_entries"
    )
    supplier_name = models.CharField(max_length=120, blank=True)
    reference_number = models.CharField(max_length=80, blank=True)
    entry_date = models.DateField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_ingredient_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Entrada {self.id}"


class IngredientStockEntryItem(models.Model):
    entry = models.ForeignKey(
        IngredientStockEntry, on_delete=models.CASCADE, related_name="items"
    )
    ingredient = models.ForeignKey(FoodIngredient, on_delete=models.PROTECT)
    purchased_quantity = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    purchase_unit = models.CharField(max_length=30, blank=True)
    conversion_factor = models.DecimalField(
        max_digits=12, decimal_places=3, default=1
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    total_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    batch_number = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return f"{self.ingredient} {self.quantity}"


class IngredientMovement(models.Model):
    MOVEMENT_IN = "in"
    MOVEMENT_OUT = "out"
    MOVEMENT_ADJUST = "adjust"
    MOVEMENT_CANCEL = "cancel"
    MOVEMENT_WASTE = "waste"
    MOVEMENT_CHOICES = [
        (MOVEMENT_IN, "Entrada"),
        (MOVEMENT_OUT, "Venda/consumo"),
        (MOVEMENT_ADJUST, "Ajuste"),
        (MOVEMENT_CANCEL, "Cancelamento/devolucao"),
        (MOVEMENT_WASTE, "Perda/desperdicio"),
    ]

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="ingredient_movements"
    )
    ingredient = models.ForeignKey(FoodIngredient, on_delete=models.PROTECT)
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=20, blank=True)
    reference_type = models.CharField(max_length=30, blank=True)
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ingredient_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "created_at"]),
            models.Index(fields=["business", "ingredient"]),
        ]

    def __str__(self):
        return f"{self.ingredient} {self.movement_type} {self.quantity}"


class DeliveryInfo(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="delivery")
    address = models.CharField(max_length=255)
    phone = models.CharField(max_length=30)
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    driver_name = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Entrega {self.order_id}"
