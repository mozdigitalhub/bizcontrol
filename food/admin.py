from django.contrib import admin

from food.models import (
    DeliveryInfo,
    FoodIngredient,
    IngredientMovement,
    IngredientStockEntry,
    IngredientStockEntryItem,
    MenuCategory,
    MenuItem,
    MenuItemRecipe,
    Order,
    OrderItem,
    OrderPayment,
    RestaurantTable,
)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("code", "business", "table", "status", "channel", "total", "created_at")
    list_filter = ("status", "channel", "business")
    search_fields = ("code",)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "menu_item", "quantity", "line_total")


@admin.register(DeliveryInfo)
class DeliveryInfoAdmin(admin.ModelAdmin):
    list_display = ("order", "address", "phone", "delivery_fee")


@admin.register(OrderPayment)
class OrderPaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "method", "amount", "paid_at")


@admin.register(FoodIngredient)
class FoodIngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "stock_qty", "is_active")
    list_filter = ("is_active", "business")
    search_fields = ("name",)


@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "is_active")
    list_filter = ("is_active", "business")
    search_fields = ("name",)


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "item_type", "selling_price", "is_active")
    list_filter = ("item_type", "is_active", "business")
    search_fields = ("name",)


@admin.register(MenuItemRecipe)
class MenuItemRecipeAdmin(admin.ModelAdmin):
    list_display = ("menu_item", "ingredient", "quantity")


@admin.register(RestaurantTable)
class RestaurantTableAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "seats", "status", "is_active")
    list_filter = ("status", "is_active", "business")
    search_fields = ("name",)


@admin.register(IngredientStockEntry)
class IngredientStockEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "business", "entry_date", "supplier_name")
    list_filter = ("business",)


@admin.register(IngredientStockEntryItem)
class IngredientStockEntryItemAdmin(admin.ModelAdmin):
    list_display = ("entry", "ingredient", "quantity")


@admin.register(IngredientMovement)
class IngredientMovementAdmin(admin.ModelAdmin):
    list_display = ("ingredient", "movement_type", "quantity", "created_at")
