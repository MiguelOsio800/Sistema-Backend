# api/models.py

from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager

# --- MODELOS DE LA FASE 2 (Sin cambios) ---

class Office(models.Model):
    name = models.CharField(max_length=100, unique=True)
    address = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True)
    # Este campo es clave para la numeración de facturas por oficina
    next_invoice_number = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.name

class Permission(models.Model):
    key = models.CharField(max_length=100, unique=True, help_text="Ej: 'invoices.create', 'flota.view'")
    description = models.CharField(max_length=255)

    def __str__(self):
        return self.key

class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    permissions = models.ManyToManyField(Permission, blank=True)

    def __str__(self):
        return self.name

class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('El usuario debe tener un nombre de usuario')
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser debe tener is_superuser=True.')
        return self.create_user(username, password, **extra_fields)

class User(AbstractUser):
    email = models.EmailField(blank=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    office = models.ForeignKey(Office, on_delete=models.SET_NULL, null=True, blank=True)
    REQUIRED_FIELDS = []
    objects = UserManager()
    def __str__(self):
        return self.username

# --- NUEVOS MODELOS DE LA FASE 3 ---

class Client(models.Model):
    """Representa a un cliente (remitente o destinatario)."""
    id_type = models.CharField(max_length=1, choices=[('V', 'V'), ('E', 'E'), ('J', 'J'), ('G', 'G')], default='V')
    id_number = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        # Asegura que no haya dos clientes con el mismo tipo y número de ID
        unique_together = ('id_type', 'id_number')

    def __str__(self):
        return f"{self.name} ({self.get_id_type_display()}-{self.id_number})"

# Reemplaza tu clase Invoice con esta
class Invoice(models.Model):
    """El modelo central: la factura o guía de envío."""
    STATUS_CHOICES = [
        ('PENDIENTE_PAGO', 'Pendiente de Pago'),
        ('PAGADA', 'Pagada'),
        ('ANULADA', 'Anulada'),
    ]
    SHIPPING_STATUS_CHOICES = [
        ('PENDIENTE_DESPACHO', 'Pendiente para Despacho'),
        ('EN_TRANSITO', 'En Tránsito'),
        ('ENTREGADA', 'Entregada'),
        ('DEVUELTA', 'Devuelta'),
    ]
    PAYMENT_TYPE_CHOICES = [
        ('flete-pagado', 'Flete Pagado'),
        ('flete-destino', 'Flete a Destino'),
    ]
    CURRENCY_CHOICES = [
        ('VES', 'Bolívares'),
        ('USD', 'Dólares'),
    ]

    invoice_number = models.CharField(max_length=20, unique=True, help_text="Número de factura único, ej: 'A-000001'")
    sender = models.ForeignKey(Client, related_name='sent_invoices', on_delete=models.PROTECT)
    recipient = models.ForeignKey(Client, related_name='received_invoices', on_delete=models.PROTECT)
    
    origin_office = models.ForeignKey(Office, related_name='origin_invoices', on_delete=models.PROTECT)
    destination_office = models.ForeignKey(Office, related_name='destination_invoices', on_delete=models.PROTECT)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    
    payment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDIENTE_PAGO')
    shipping_status = models.CharField(max_length=20, choices=SHIPPING_STATUS_CHOICES, default='PENDIENTE_DESPACHO')
    
    # --- CAMPOS NUEVOS AÑADIDOS ---
    shipping_type = models.ForeignKey('ShippingType', on_delete=models.SET_NULL, null=True, blank=True)
    payment_method = models.ForeignKey('PaymentMethod', on_delete=models.SET_NULL, null=True, blank=True)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='flete-pagado')
    payment_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='VES')
    has_insurance = models.BooleanField(default=False)
    declared_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    insurance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    has_discount = models.BooleanField(default=False)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    # --- FIN DE CAMPOS NUEVOS ---

    # Campos financieros
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax = models.DecimalField(max_digits=12, decimal_places=2) # IVA
    ipostel = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    igtf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    
    def __str__(self):
        return f"Factura {self.invoice_number} - {self.sender.name} a {self.recipient.name}"

# Reemplaza tu clase MerchandiseItem con esta
class MerchandiseItem(models.Model):
    """Representa un item dentro de una factura."""
    invoice = models.ForeignKey(Invoice, related_name='items', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    description = models.CharField(max_length=255)
    weight = models.DecimalField(max_digits=10, decimal_places=2, help_text="Peso real en Kg")
    
    # --- CAMPOS NUEVOS AÑADIDOS ---
    length = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    width = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    height = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True)
    # --- FIN DE CAMPOS NUEVOS ---
    
    def __str__(self):
        return f"{self.quantity} x {self.description} (Factura: {self.invoice.invoice_number})"
    

class Vehicle(models.Model):
    """Representa un vehículo de la flota."""
    STATUS_CHOICES = [
        ('Disponible', 'Disponible'),
        ('En Ruta', 'En Ruta'),
        ('En Mantenimiento', 'En Mantenimiento'),
    ]
    license_plate = models.CharField(max_length=10, unique=True)
    brand = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    year = models.PositiveIntegerField()
    capacity_kg = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Disponible')
    driver = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to='vehicles/', null=True, blank=True)

    def __str__(self):
        return f"{self.brand} {self.model} ({self.license_plate})"

class ShipmentManifest(models.Model):
    """Representa una remesa o manifiesto de carga para un viaje."""
    STATUS_CHOICES = [
        ('PLANIFICADO', 'Planificado'),
        ('EN_RUTA', 'En Ruta'),
        ('FINALIZADO', 'Finalizado'),
    ]
    manifest_number = models.CharField(max_length=20, unique=True)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT)
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    departure_time = models.DateTimeField(null=True, blank=True)
    arrival_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANIFICADO')

    def __str__(self):
        return f"Manifiesto {self.manifest_number} (Vehículo: {self.vehicle.license_plate})"

class MerchandiseItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name='items', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    description = models.CharField(max_length=255)
    weight = models.DecimalField(max_digits=10, decimal_places=2, help_text="Peso real en Kg")
    def __str__(self): return f"{self.quantity} x {self.description} (Factura: {self.invoice.invoice_number})"


class Expense(models.Model):
    """Representa un gasto operativo de la empresa."""
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.CharField(max_length=100, blank=True) # Ej: Combustible, Sueldos, Alquiler
    office = models.ForeignKey(Office, on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Gasto: {self.description} - {self.amount}"
    
class AuditLog(models.Model):
    """Registra una acción importante realizada en el sistema."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255, help_text="Ej: 'Creación de factura', 'Inicio de sesión'")
    details = models.TextField(blank=True, help_text="Detalles adicionales, como el ID del objeto afectado.")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp} - {self.user}: {self.action}"

class CompanyInfo(models.Model):
    """Modelo Singleton para guardar la configuración de la empresa."""
    name = models.CharField(max_length=255, default="Transporte Alianza 2025 C.A.")
    rif = models.CharField(max_length=20)
    address = models.TextField()
    phone = models.CharField(max_length=50)
    
    # --- CAMBIOS AQUÍ ---
    # Se elimina el antiguo logo_url y se reemplaza por campos de imagen reales
    logo = models.ImageField(upload_to='company/', null=True, blank=True)
    login_image = models.ImageField(upload_to='company/', null=True, blank=True)
    postal_license = models.CharField(max_length=50, blank=True) # Campo añadido
    # --- FIN DE CAMBIOS ---
    
    cost_per_kg = models.DecimalField(max_digits=10, decimal_places=2, default=1.0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=16.0, help_text="Tasa de IVA en porcentaje (ej: 16.0)")
    bcv_rate = models.DecimalField(max_digits=10, decimal_places=2, default=36.5)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.pk = 1
        super(CompanyInfo, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
    
class Supplier(models.Model):
    """Representa a un proveedor de bienes o servicios."""
    name = models.CharField(max_length=255, unique=True)
    rif = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

class AssetCategory(models.Model):
    """Categoría para los bienes de la empresa. Ej: 'Equipo de computación', 'Mobiliario'."""
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name

class Asset(models.Model):
    """Representa un bien o activo fijo de la empresa."""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(AssetCategory, on_delete=models.SET_NULL, null=True)
    office = models.ForeignKey(Office, on_delete=models.SET_NULL, null=True, help_text="Ubicación del bien")
    purchase_date = models.DateField(null=True, blank=True)
    purchase_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    def __str__(self):
        return self.name

# --- CAMBIO: AÑADIR NUEVOS MODELOS DE CONFIGURACIÓN ---

class ShippingType(models.Model):
    """Define las modalidades de envío, ej: Básico, Expreso."""
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class PaymentMethod(models.Model):
    """Define las formas de pago aceptadas."""
    TYPE_CHOICES = [
        ('Efectivo', 'Efectivo'),
        ('Transferencia', 'Transferencia'),
        ('PagoMovil', 'Pago Móvil'),
        ('Credito', 'Crédito'),
        ('Otro', 'Otro'),
    ]
    name = models.CharField(max_length=100) # Ej: "Cuenta Ahorro Banesco"
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='Efectivo')
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=20, blank=True)
    beneficiary_name = models.CharField(max_length=255, blank=True)
    beneficiary_id = models.CharField(max_length=20, blank=True) # RIF o Cédula
    phone = models.CharField(max_length=20, blank=True) # Para Pago Móvil
    email = models.EmailField(blank=True)
    
    def __str__(self):
        return self.name

class ExpenseCategory(models.Model):
    """Categorías para los gastos operativos."""
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Category(models.Model):
    """Categorías para la mercancía."""
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
