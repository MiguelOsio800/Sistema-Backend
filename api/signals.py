# api/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Invoice, Expense, AuditLog, User

# Este decorador conecta nuestra función a la señal 'post_save' para el modelo Invoice
@receiver(post_save, sender=Invoice)
def log_invoice_creation(sender, instance, created, **kwargs):
    """
    Registra en la auditoría cuando se crea una nueva factura.
    """
    if created: # 'created' es True solo la primera vez que se guarda el objeto
        AuditLog.objects.create(
            user=instance.created_by,
            action="Creación de Factura",
            details=f"Se creó la factura N° {instance.invoice_number} por un total de {instance.total}."
        )

@receiver(post_save, sender=Expense)
def log_expense_creation(sender, instance, created, **kwargs):
    """
    Registra en la auditoría cuando se crea un nuevo gasto.
    """
    if created:
        AuditLog.objects.create(
            user=instance.created_by,
            action="Registro de Gasto",
            details=f"Se registró un gasto de '{instance.description}' por un monto de {instance.amount}."
        )

# Podríamos añadir más señales para login, modificación de usuarios, etc.
# Por ahora, estas dos son un excelente ejemplo.