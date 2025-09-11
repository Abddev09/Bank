# transfer/urls.py
from django.urls import path
from .views import jsonrpc

urlpatterns = [
    path("cards/",jsonrpc, name="jsonrpc_cards"),
]