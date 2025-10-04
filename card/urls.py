# transfer/urls.py
from django.urls import path
from .views import jsonrpc, card_import_rest

urlpatterns = [
    path("cards/",jsonrpc, name="jsonrpc_cards"),
    path("cards/import/", card_import_rest, name="card_import_rest"),
]