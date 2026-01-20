from django.db import transaction
from django.utils import timezone

from tenants.models import DocumentSequence


def generate_document_code(*, business, doc_type, prefix, date=None):
    seq_date = date or timezone.localdate()
    with transaction.atomic():
        seq = (
            DocumentSequence.objects.select_for_update()
            .filter(business=business, doc_type=doc_type, seq_date=seq_date)
            .first()
        )
        if not seq:
            seq = DocumentSequence.objects.create(
                business=business, doc_type=doc_type, seq_date=seq_date, current_value=0
            )
        seq.current_value += 1
        seq.save(update_fields=["current_value"])
        seq_value = seq.current_value
    return f"{prefix}-{seq_date.strftime('%y%m%d')}-{business.id}-{seq_value:03d}"
