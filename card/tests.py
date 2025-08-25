from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from card.models import Card

class CardTests(APITestCase):
    def test_add_card_valid(self):
        url = reverse('cards-add-card')  # router orqali avtomatik hosil bo‘ladi
        data = {
            "card_number": "1234567812345678",
            "expire": "12/25",
            "phone": "998901234567",
            "status": "active",
            "balance": "1000.00"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Card.objects.count(), 1)

    def test_add_card_invalid_card_number(self):
        url = reverse('cards-add-card')
        data = {
            "card_number": "123",  # invalid
            "expire": "12/25",
            "phone": "998901234567",
            "status": "active",
            "balance": "1000.00"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('card_number', response.data)
