from rest_framework import generics, viewsets, status
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Sum, Count
from django.utils import timezone
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction # Se importa transaction que faltaba
from .models import (
    User, Client, Invoice, Vehicle, ShipmentManifest, Expense, Office, AuditLog, CompanyInfo,
    Role, Permission, Supplier, AssetCategory, Asset, ShippingType, PaymentMethod, ExpenseCategory, Category
)
from .serializers import (
    RegisterUserSerializer, UserSerializer, ClientSerializer, 
    InvoiceSerializer, CreateInvoiceSerializer, VehicleSerializer,
    ShipmentManifestSerializer, DispatchSerializer, ExpenseSerializer,
    AuditLogSerializer, CompanyInfoSerializer, SupplierSerializer,
    AssetCategorySerializer, AssetSerializer, CreateAssetSerializer,
    RoleSerializer, PermissionSerializer, OfficeSerializer,
    ShippingTypeSerializer, PaymentMethodSerializer, ExpenseCategorySerializer, CategorySerializer
)

# --- VISTAS DE LA FASE 2 (Sin cambios) ---
class RegisterUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterUserSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    user = request.user
    serializer = UserSerializer(user, context={'request': request})
    return Response(serializer.data)

# --- NUEVAS VISTAS DE LA FASE 3 ---

class ClientViewSet(viewsets.ModelViewSet):
    """API endpoint para ver y editar clientes."""
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]

class InvoiceViewSet(viewsets.ModelViewSet):
    """
    API endpoint para facturas.
    Usa un serializer diferente para 'create' vs 'list'/'retrieve'.
    """
    queryset = Invoice.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateInvoiceSerializer
        return InvoiceSerializer
    
    def get_queryset(self):
        """
        Filtra las facturas para que los usuarios solo vean lo que les corresponde.
        - Admin General ve todo.
        - Admin de Oficina ve todas las de su oficina.
        - Usuario Normal solo ve las que él creó.
        """
        user = self.request.user
        
        if user.is_superuser or (user.role and user.role.name == 'Admin General'):
            return Invoice.objects.all().order_by('-created_at')
        
        if user.role and user.role.name == 'Admin de Oficina':
            return Invoice.objects.filter(origin_office=user.office).order_by('-created_at')
            
        return Invoice.objects.filter(created_by=user).order_by('-created_at')
    

class VehicleViewSet(viewsets.ModelViewSet):
    """API endpoint para la flota de vehículos."""
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

class ShipmentManifestViewSet(viewsets.ModelViewSet):
    """API endpoint para los manifiestos de carga (remesas)."""
    queryset = ShipmentManifest.objects.all().order_by('-id')
    serializer_class = ShipmentManifestSerializer
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def dispatch(self, request, pk=None):
        """Acción para despachar un manifiesto con sus facturas."""
        manifest = self.get_object()
        serializer = DispatchSerializer(instance=manifest, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'manifiesto despachado'}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def finalize_trip(self, request, pk=None):
        """Acción para finalizar un viaje."""
        manifest = self.get_object()
        with transaction.atomic():
            if manifest.status != 'EN_RUTA':
                return Response({'error': 'El manifiesto no está en ruta.'}, status=status.HTTP_400_BAD_REQUEST)
            
            manifest.status = 'FINALIZADO'
            manifest.arrival_time = timezone.now()
            manifest.save()
            
            vehicle = manifest.vehicle
            vehicle.status = 'DISPONIBLE'
            vehicle.save()
            
            manifest.invoices.all().update(shipping_status='ENTREGADA')
            
            return Response({'status': 'viaje finalizado, facturas entregadas'}, status=status.HTTP_200_OK)
        
class ExpenseViewSet(viewsets.ModelViewSet):
    """API endpoint para los gastos operativos."""
    queryset = Expense.objects.all().order_by('-created_at')
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filtra los gastos por usuario/oficina, similar a las facturas."""
        user = self.request.user
        if user.is_superuser:
            return Expense.objects.all().order_by('-created_at')
        return Expense.objects.filter(office=user.office).order_by('-created_at')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_dashboard_stats(request):
    """
    Calcula y devuelve las estadísticas principales para el Dashboard.
    """
    now = timezone.now()
    total_revenue = Invoice.objects.filter(
        created_at__year=now.year,
        created_at__month=now.month
    ).exclude(payment_status='ANULADA').aggregate(total=Sum('total'))['total'] or 0
    total_expenses = Expense.objects.filter(
        created_at__year=now.year,
        created_at__month=now.month
    ).aggregate(total=Sum('amount'))['total'] or 0
    shipping_status_counts = Invoice.objects.values('shipping_status').annotate(count=Count('id'))
    stats = {
        'total_revenue_month': total_revenue,
        'total_expenses_month': total_expenses,
        'net_income_month': total_revenue - total_expenses,
        'shipping_status_counts': {item['shipping_status']: item['count'] for item in shipping_status_counts}
    }
    return Response(stats)

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint para ver los registros de auditoría."""
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser]

class CompanyInfoView(APIView):
    permission_classes = [IsAuthenticated]
    # --- CAMBIO APLICADO AQUÍ ---
    parser_classes = (MultiPartParser, FormParser,)

    def get(self, request, *args, **kwargs):
        company_info = CompanyInfo.load()
        serializer = CompanyInfoSerializer(company_info)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        if not request.user.is_staff:
             return Response({'detail': 'No tienes permiso para realizar esta acción.'}, status=status.HTTP_403_FORBIDDEN)
        company_info = CompanyInfo.load()
        # --- CAMBIO APLICADO AQUÍ (partial=True permite no enviar todos los campos) ---
        serializer = CompanyInfoSerializer(company_info, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    
class SupplierViewSet(viewsets.ModelViewSet):
    """API endpoint para Proveedores."""
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]

class AssetCategoryViewSet(viewsets.ModelViewSet):
    """API endpoint para Categorías de Bienes."""
    queryset = AssetCategory.objects.all()
    serializer_class = AssetCategorySerializer
    # CAMBIO: Se permite a cualquier usuario autenticado LEER.
    permission_classes = [IsAuthenticated]

class AssetViewSet(viewsets.ModelViewSet):
    """API endpoint para Bienes/Activos."""
    queryset = Asset.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create' or self.action == 'update':
            return CreateAssetSerializer
        return AssetSerializer

# --- VISTAS PARA PARÁMETROS DE CONFIGURACIÓN ---

class OfficeViewSet(viewsets.ModelViewSet):
    queryset = Office.objects.all()
    serializer_class = OfficeSerializer
    # CAMBIO: Se permite a cualquier usuario autenticado LEER.
    permission_classes = [IsAuthenticated]

class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    # CAMBIO: Se permite a cualquier usuario autenticado LEER.
    permission_classes = [IsAuthenticated]
    
class PermissionViewSet(viewsets.ModelViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    # CAMBIO: Se permite a cualquier usuario autenticado LEER.
    permission_classes = [IsAuthenticated]

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    # CAMBIO: Se permite a cualquier usuario autenticado LEER.
    permission_classes = [IsAuthenticated]

# --- CAMBIO: AÑADIR NUEVAS VISTAS (VIEWSETS) ---

class ShippingTypeViewSet(viewsets.ModelViewSet):
    """API endpoint para Tipos de Envío."""
    queryset = ShippingType.objects.all()
    serializer_class = ShippingTypeSerializer
    permission_classes = [IsAuthenticated]

class PaymentMethodViewSet(viewsets.ModelViewSet):
    """API endpoint para Formas de Pago."""
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated]

class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    """API endpoint para Categorías de Gasto."""
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated]

class CategoryViewSet(viewsets.ModelViewSet):
    """API endpoint para Categorías de Mercancía."""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
