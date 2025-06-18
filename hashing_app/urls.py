from django.urls import path
from .views import HashingOperationView, HashingStateView, ResetHashingStateView, HashingLogsView

urlpatterns = [
    path('<str:algorithm_type>/', HashingOperationView.as_view(), name='hashing_operation'),
    path('<str:algorithm_type>/state/', HashingStateView.as_view(), name='hashing_state'),
    path('<str:algorithm_type>/reset/', ResetHashingStateView.as_view(), name='reset_hashing_state'),
    path('logs/mysql/', HashingLogsView.as_view(), name='mysql_logs'), # Cambiado a mysql_logs
]