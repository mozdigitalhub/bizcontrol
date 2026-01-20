from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Q

from tenants.models import Business


class Customer(models.Model):
    TYPE_INDIVIDUAL = "individual"
    TYPE_COMPANY = "company"
    TYPE_CHOICES = [
        (TYPE_INDIVIDUAL, "Particular"),
        (TYPE_COMPANY, "Empresa"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="customers")
    customer_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default=TYPE_INDIVIDUAL
    )
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    nuit = models.CharField(max_length=30, blank=True)
    credit_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_customers",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_customers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["business", "name"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "phone"],
                condition=~Q(phone=""),
                name="uniq_customer_phone_business",
            )
        ]

    def __str__(self):
        return self.name
