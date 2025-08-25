# transfer/tests.py
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from card.models import Card
from transfer.models import Transfer
from unittest.mock import patch

@patch('card.utils.send_bulk')  # send_bulk funksiyasini test davomida mock qilamiz
class TransferTests(APITestCase):

    def setUp(self):
        self.sender = Card.objects.create(
            card_number="9860080121420432",
            expire="02/27",
            phone="+998887091228",
            status='active',
            balance=100.0
        )
        self.receiver = Card.objects.create(
            card_number="2284370384722343",
            expire="09/29",
            phone="+998777412154",
            status='active',
            balance=56.2
        )

    def test_add_transfer_valid(self, mock_send):
        mock_send.return_value = None  # Telegramga xabar yubormaslik
        url = reverse('transfers-add-transfer')
        data = {
            "sender_card_number": self.sender.card_number,
            "receiver_card_number": self.receiver.card_number,
            "sender_card_expiry": self.sender.expire,
            "sending_amount": 50,
            "currency": "860"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Transfer.objects.count(), 1)
        transfer = Transfer.objects.first()
        self.assertEqual(transfer.sender_card_number, self.sender.card_number)
        self.assertEqual(transfer.receiver_card_number, self.receiver.card_number)
        self.assertEqual(transfer.state, 'created')
        self.assertIsNotNone(transfer.ext_id)
        self.assertIsNotNone(transfer.otp)

    def test_add_transfer_insufficient_balance(self, mock_send):
        mock_send.return_value = None
        url = reverse('transfers-add-transfer')
        data = {
            "sender_card_number": self.sender.card_number,
            "receiver_card_number": self.receiver.card_number,
            "sender_card_expiry": self.sender.expire,
            "sending_amount": 500,
            "currency": "860"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('sending_amount', response.data)
        self.assertIn('code', response.data['sending_amount'])
        self.assertIn('message', response.data['sending_amount'])

    def test_add_transfer_inactive_sender(self, mock_send):
        mock_send.return_value = None
        self.sender.status = 'inactive'
        self.sender.save()
        url = reverse('transfers-add-transfer')
        data = {
            "sender_card_number": self.sender.card_number,
            "receiver_card_number": self.receiver.card_number,
            "sender_card_expiry": self.sender.expire,
            "sending_amount": 50,
            "currency": "860"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('sender_card_number', response.data)
        self.assertIn('code', response.data['sender_card_number'])
        self.assertIn('message', response.data['sender_card_number'])
