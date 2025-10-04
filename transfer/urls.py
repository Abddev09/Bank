# transfer/urls.py
from django.urls import path
from .views import jsonrpc

urlpatterns = [
    path("transfers/",jsonrpc, name="jsonrpc_transfer"),
]