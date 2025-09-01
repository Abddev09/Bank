# transfer/urls.py
from django.urls import path
from .views import JSONRPCView

urlpatterns = [
    path("transfer/", JSONRPCView.as_view(), name="jsonrpc_transfer"),
]