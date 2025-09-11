import json
from django.test import TestCase, Client
from django.utils import timezone
from card.models import Card
from transfer.models import Transfer


class TransferRpcTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Sender va Receiver kartalarini yaratamiz
        self.sender = Card.objects.create(
            card_number="8600123412341234",
            expire="12/30",
            phone="+998901112233",
            status="active",
            balance=1000000
        )
        self.receiver = Card.objects.create(
            card_number="8600432112345678",
            expire="11/29",
            phone="+998909998877",
            status="active",
            balance=500000
        )

    def rpc_call(self, method, params=None):
        req = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1
        }
        response = self.client.post(
            "/api/transfers/",
            data=json.dumps(req),
            content_type="application/json"
        )
        return json.loads(response.content)

    def test_transfer_create_success(self):
        """Transfer yaratish muvaffaqiyatli bo‘lishi kerak"""
        resp = self.rpc_call("transfer.create", {
            "sender_card_number": self.sender.card_number,
            "receiver_card_number": self.receiver.card_number,
            "sender_card_expiry": self.sender.expire,
            "sending_amount": 1000,
            "currency": "860",
        })
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["otp_sent"], True)

    def test_transfer_create_missing_field(self):
        """Majburiy field yo‘qligida xatolik qaytishi kerak"""
        resp = self.rpc_call("transfer.create", {
            "sender_card_number": self.sender.card_number,
            # receiver_card_number kiritilmagan
            "sender_card_expiry": self.sender.expire,
            "sending_amount": 1000,
            "currency": "860",
        })
        self.assertIn("error", resp)

    def test_transfer_state(self):
        """Transfer state tekshirish"""
        transfer = Transfer.objects.create(
            ext_id="tr-123",
            sender_card_number=self.sender.card_number,
            receiver_card_number=self.receiver.card_number,
            sender_card_expiry=self.sender.expire,
            sending_amount=2000,
            currency="860",
            sender_phone=self.sender.phone,
            receiver_phone=self.receiver.phone,
            state=1,
            otp="123456"
        )
        resp = self.rpc_call("transfer.state", {"ext_id": transfer.ext_id})
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["ext_id"], transfer.ext_id)
        self.assertEqual(resp["result"]["state"], 1)

    def test_transfer_cancel(self):
        """Transfer cancel"""
        transfer = Transfer.objects.create(
            ext_id="tr-456",
            sender_card_number=self.sender.card_number,
            receiver_card_number=self.receiver.card_number,
            sender_card_expiry=self.sender.expire,
            sending_amount=2000,
            currency="860",
            sender_phone=self.sender.phone,
            receiver_phone=self.receiver.phone,
            state=1,
            otp="123456"
        )
        resp = self.rpc_call("transfer.cancel", {"ext_id": transfer.ext_id})
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["state"],3)

    def test_transfer_history(self):
        """Tarixni chiqarish"""
        Transfer.objects.create(
            ext_id="tr-789",
            sender_card_number=self.sender.card_number,
            receiver_card_number=self.receiver.card_number,
            sender_card_expiry=self.sender.expire,
            sending_amount=3000,
            currency="860",
            sender_phone=self.sender.phone,
            receiver_phone=self.receiver.phone,
            state=2,
            otp="123456",
            created_at=timezone.now()
        )
        resp = self.rpc_call("transfer.history", {
            "card_number": self.sender.card_number,
            "start_date": "2020-01-01",
            "end_date": "2030-01-01",
        })
        self.assertIn("result", resp)
        self.assertTrue(len(resp["result"]) > 0)
