from django.db import models


class ReportAccess(models.Model):
    label = models.CharField(max_length=120, blank=True)

    class Meta:
        permissions = (
            ("view_basic", "Pode ver relatorios basicos"),
            ("view_finance", "Pode ver relatorios financeiros"),
            ("view_stock", "Pode ver relatorios de stock"),
            ("export", "Pode exportar relatorios"),
        )

    def __str__(self):
        return self.label or "Relatorios"
