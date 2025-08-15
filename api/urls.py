# api/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterUserView, get_user_profile,
    ClientViewSet, InvoiceViewSet, VehicleViewSet, ShipmentManifestViewSet,
    ExpenseViewSet, get_dashboard_stats, AuditLogViewSet, CompanyInfoView,
    SupplierViewSet, AssetCategoryViewSet, AssetViewSet, OfficeViewSet,
    RoleViewSet, PermissionViewSet, UserViewSet,
    # CAMBIO: Importar las nuevas vistas
    ShippingTypeViewSet, PaymentMethodViewSet, ExpenseCategoryViewSet, CategoryViewSet
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

router = DefaultRouter()
router.register(r'clients', ClientViewSet)
router.register(r'invoices', InvoiceViewSet)
router.register(r'vehicles', VehicleViewSet)
router.register(r'manifests', ShipmentManifestViewSet)
router.register(r'expenses', ExpenseViewSet)
router.register(r'audit-logs', AuditLogViewSet)
router.register(r'suppliers', SupplierViewSet)
router.register(r'asset-categories', AssetCategoryViewSet)
router.register(r'assets', AssetViewSet)
router.register(r'offices', OfficeViewSet)
router.register(r'roles', RoleViewSet)
router.register(r'permissions', PermissionViewSet)
router.register(r'users', UserViewSet)
# CAMBIO: Registrar las nuevas rutas
router.register(r'shipping-types', ShippingTypeViewSet)
router.register(r'payment-methods', PaymentMethodViewSet)
router.register(r'expense-categories', ExpenseCategoryViewSet)
router.register(r'categories', CategoryViewSet)


urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterUserView.as_view(), name='auth_register'),
    path('profile/', get_user_profile, name='user_profile'),
    path('dashboard-stats/', get_dashboard_stats, name='dashboard_stats'),
    path('company-info/', CompanyInfoView.as_view(), name='company-info'),
    path('', include(router.urls)),
]