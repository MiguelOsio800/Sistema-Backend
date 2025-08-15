# api/admin.py

from django.contrib import admin
from .models import (
    User, Role, Office, Permission, Client, Invoice, MerchandiseItem,
    Vehicle, ShipmentManifest, Expense, AuditLog, CompanyInfo,
    Supplier, AssetCategory, Asset,
    # CAMBIO: Importar los nuevos modelos
    ShippingType, PaymentMethod, ExpenseCategory, Category
)

# Creamos una clase especial para mejorar la visualización de los Roles
class RoleAdmin(admin.ModelAdmin):
    # Esto le dice a Django que muestre el campo 'permissions' 
    # con un widget de filtro horizontal, que es mucho más cómodo.
    filter_horizontal = ('permissions',)

# Registramos los modelos existentes
admin.site.register(User)
admin.site.register(Office)
admin.site.register(Permission)
admin.site.register(Client)
admin.site.register(Invoice)
admin.site.register(MerchandiseItem)
admin.site.register(Vehicle)
admin.site.register(ShipmentManifest)
admin.site.register(Expense)
admin.site.register(AuditLog)
admin.site.register(CompanyInfo)
admin.site.register(Supplier)
admin.site.register(AssetCategory)
admin.site.register(Asset)

# CAMBIO: Registrar los nuevos modelos
admin.site.register(ShippingType)
admin.site.register(PaymentMethod)
admin.site.register(ExpenseCategory)
admin.site.register(Category)


# CAMBIO: Le decimos a Django que use nuestra clase personalizada para el modelo Role
admin.site.register(Role, RoleAdmin)