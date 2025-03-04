from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import PurchaseItem

@receiver(pre_save, sender=PurchaseItem)
def purchase_item_pre_save(sender, instance, **kwargs):
    if not instance.purchase_id:  # Agar Purchase ob'ekti hali saqlanmagan bo'lsa
        raise ValueError("Purchase object must be saved before its items.")