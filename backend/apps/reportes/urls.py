from django.urls import path

from apps.reportes.views import DashboardViewSet

urlpatterns = [
    path('dashboard/', DashboardViewSet.as_view({'get': 'list'}), name='dashboard'),
    path('dashboard/servicios-por-tecnico/',
         DashboardViewSet.as_view({'get': 'servicios_por_tecnico'}),
         name='dashboard-servicios-por-tecnico'),
    path('dashboard/instalaciones-por-mes/',
         DashboardViewSet.as_view({'get': 'instalaciones_por_mes'}),
         name='dashboard-instalaciones-por-mes'),
    path('dashboard/servicios-por-mes/',
         DashboardViewSet.as_view({'get': 'servicios_por_mes'}),
         name='dashboard-servicios-por-mes'),
    path('dashboard/materiales-stock-bajo/',
         DashboardViewSet.as_view({'get': 'materiales_stock_bajo'}),
         name='dashboard-materiales-stock-bajo'),
    path('dashboard/exportar/',
         DashboardViewSet.as_view({'get': 'exportar'}),
         name='dashboard-exportar'),
    path('reportes/',
         DashboardViewSet.as_view({'get': 'reportes_list'}),
         name='reportes'),
]
