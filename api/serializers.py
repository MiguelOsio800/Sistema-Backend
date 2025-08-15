# api/serializers.py

from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from .models import (
    User, Role, Office, Permission, Client, Invoice, MerchandiseItem,
    Vehicle, ShipmentManifest, Expense, AuditLog, CompanyInfo,
    Supplier, AssetCategory, Asset, ShippingType, PaymentMethod, ExpenseCategory, Category
)

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['key']

class OfficeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Office
        fields = '__all__'

class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    class Meta:
        model = Role
        fields = ['id', 'name', 'permissions']
    def get_permissions(self, obj):
        return {perm.key: True for perm in obj.permissions.all()}

class UserSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    office = OfficeSerializer(read_only=True)
    roleId = serializers.PrimaryKeyRelatedField(source='role', read_only=True)
    officeId = serializers.PrimaryKeyRelatedField(source='office', read_only=True)
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 'office', 'roleId', 'officeId', 'is_active', 'last_login')

class RegisterUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'password', 'role', 'office')
        extra_kwargs = {'password': {'write_only': True}}
    def create(self, validated_data):
        user = User.objects.create_user(username=validated_data['username'], password=validated_data['password'], role=validated_data.get('role'), office=validated_data.get('office'))
        return user

# --- CAMBIO AQUÍ: SERIALIZER DE CLIENTE REESCRITO PARA MÁXIMA COMPATIBILIDAD ---
class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__' # Esto aceptará directamente id_type, id_number, etc.

class MerchandiseItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MerchandiseItem
        fields = ('quantity', 'description', 'weight')

class InvoiceSerializer(serializers.ModelSerializer):
    sender = ClientSerializer()
    recipient = ClientSerializer()
    items = MerchandiseItemSerializer(many=True, read_only=True)
    class Meta:
        model = Invoice
        fields = '__all__'

# Reemplaza tu clase CreateInvoiceSerializer con esta
class CreateInvoiceSerializer(serializers.ModelSerializer):
    sender = ClientSerializer()
    recipient = ClientSerializer()
    items = MerchandiseItemSerializer(many=True)
    
    # Nuevos campos para recibir IDs desde el frontend
    destination_office_id = serializers.IntegerField(write_only=True)
    shipping_type_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    payment_method_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Invoice
        # Lista completa de todos los campos que el frontend enviará
        fields = (
            'sender', 'recipient', 'items', 'subtotal', 'tax', 'ipostel', 'igtf', 'total',
            'destination_office_id', 'shipping_type_id', 'payment_method_id', 'payment_type', 
            'payment_currency', 'has_insurance', 'declared_value', 'insurance_percentage',
            'has_discount', 'discount_percentage'
        )

    def create(self, validated_data):
        with transaction.atomic():
            sender_data = validated_data.pop('sender')
            recipient_data = validated_data.pop('recipient')
            items_data = validated_data.pop('items')

            sender, _ = Client.objects.get_or_create(**sender_data)
            recipient, _ = Client.objects.get_or_create(**recipient_data)
            
            user = self.context['request'].user
            origin_office = user.office
            if not origin_office:
                raise serializers.ValidationError("El usuario no tiene una oficina de origen asignada.")

            # Generar número de factura
            office_for_update = Office.objects.select_for_update().get(pk=origin_office.pk)
            invoice_num_part = office_for_update.next_invoice_number
            office_prefix = origin_office.name[0].upper()
            invoice_number = f"{office_prefix}-{str(invoice_num_part).zfill(6)}"
            office_for_update.next_invoice_number += 1
            office_for_update.save()

            # Crear la factura con todos los datos
            invoice = Invoice.objects.create(
                sender=sender, 
                recipient=recipient, 
                created_by=user, 
                origin_office=origin_office, 
                invoice_number=invoice_number, 
                **validated_data
            )
            
            # Crear los items de mercancía
            for item_data in items_data:
                MerchandiseItem.objects.create(invoice=invoice, **item_data)
            
            return invoice

class VehicleSerializer(serializers.ModelSerializer):
    # Añadimos un validador explícito para el campo de imagen
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Vehicle
        fields = '__all__'

    def validate_image(self, value):
        """
        Valida que el archivo subido sea JPG o PNG.
        """
        if value:
            # Obtiene el tipo de contenido del archivo
            main, sub = value.content_type.split('/')
            if not (main == 'image' and sub in ['jpeg', 'png']):
                raise serializers.ValidationError("Solo se permiten imágenes en formato JPG o PNG.")
        return value

class ShipmentManifestSerializer(serializers.ModelSerializer):
    invoices = InvoiceSerializer(many=True, read_only=True)
    class Meta:
        model = ShipmentManifest
        fields = '__all__'
        read_only_fields = ('manifest_number', 'status', 'departure_time', 'arrival_time')

class DispatchSerializer(serializers.Serializer):
    invoice_ids = serializers.ListField(child=serializers.IntegerField())
    driver_id = serializers.IntegerField(required=False)
    def update(self, instance, validated_data):
        # ... (lógica de despacho sin cambios)
        invoice_ids = validated_data.get('invoice_ids'); driver_id = validated_data.get('driver_id')
        with transaction.atomic():
            if instance.status != 'PLANIFICADO': raise serializers.ValidationError("Este manifiesto ya ha sido despachado o finalizado.")
            vehicle = instance.vehicle
            if vehicle.status != 'DISPONIBLE': raise serializers.ValidationError(f"El vehículo {vehicle.license_plate} no está disponible.")
            if driver_id:
                try: driver = User.objects.get(pk=driver_id); instance.driver = driver
                except User.DoesNotExist: raise serializers.ValidationError("El conductor especificado no existe.")
            invoices_to_dispatch = Invoice.objects.filter(pk__in=invoice_ids, shipping_status='PENDIENTE_DESPACHO')
            if len(invoices_to_dispatch) != len(invoice_ids): raise serializers.ValidationError("Una o más facturas no existen o no están pendientes para despacho.")
            invoices_to_dispatch.update(manifest=instance, shipping_status='EN_TRANSITO')
            instance.status = 'EN_RUTA'; instance.departure_time = timezone.now(); instance.save()
            vehicle.status = 'EN_RUTA'; vehicle.save()
            return instance

class ExpenseSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    office = serializers.StringRelatedField(read_only=True)
    class Meta:
        model = Expense
        fields = '__all__'
    def create(self, validated_data):
        # ... (lógica de creación de gasto sin cambios)
        user = self.context['request'].user
        office = user.office
        if not office: raise serializers.ValidationError("El usuario debe estar asignado a una oficina para registrar gastos.")
        expense = Expense.objects.create(created_by=user, office=office, **validated_data)
        return expense
        
class AuditLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    class Meta:
        model = AuditLog
        fields = '__all__'

class CompanyInfoSerializer(serializers.ModelSerializer):
    # Campos que se envían al frontend (solo lectura)
    logoUrl = serializers.ImageField(source='logo', read_only=True)
    loginImageUrl = serializers.ImageField(source='login_image', read_only=True)
    postalLicense = serializers.CharField(source='postal_license', required=False, allow_blank=True)
    costPerKg = serializers.DecimalField(source='cost_per_kg', max_digits=10, decimal_places=2)
    bcvRate = serializers.DecimalField(source='bcv_rate', max_digits=10, decimal_places=2)
    taxRate = serializers.DecimalField(source='tax_rate', max_digits=5, decimal_places=2)

    # Campos para recibir datos (escritura)
    logo = serializers.ImageField(write_only=True, required=False, allow_null=True)
    login_image = serializers.ImageField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = CompanyInfo
        fields = (
            'name', 'rif', 'address', 'phone', 
            'logoUrl', 'loginImageUrl', 'postalLicense', 
            'costPerKg', 'bcvRate', 'taxRate',
            # Campos que se reciben del formulario
            'logo', 'login_image', 'postal_license', 'cost_per_kg', 'bcv_rate', 'tax_rate'
        )
    
    # Validadores de imagen como en el VehicleSerializer
    def validate_image(self, value, field_name):
        if value:
            main, sub = value.content_type.split('/')
            if not (main == 'image' and sub in ['jpeg', 'png', 'gif']):
                raise serializers.ValidationError(f"Para '{field_name}', solo se permiten imágenes JPG o PNG.")
        return value

    def validate_logo(self, value):
        return self.validate_image(value, 'logo')

    def validate_login_image(self, value):
        return self.validate_image(value, 'login_image')

class SupplierSerializer(serializers.ModelSerializer):
    # Mapea los nombres del frontend al backend
    idNumber = serializers.CharField(source='rif', required=False, allow_blank=True)

    class Meta:
        model = Supplier
        fields = ('id', 'name', 'phone', 'address', 'rif', 'idNumber')
        read_only_fields = ('rif',)

class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = '__all__'
        
class AssetSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()
    office = serializers.StringRelatedField()
    class Meta:
        model = Asset
        fields = '__all__'

class CreateAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = '__all__'

# --- CAMBIO: AÑADIR NUEVOS SERIALIZADORES ---

class ShippingTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingType
        fields = '__all__'

class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = '__all__'

class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = '__all__'

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'