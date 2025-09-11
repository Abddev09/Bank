import os
import tempfile
import json
import pandas as pd
from django.test import TestCase, Client
from django.core.cache import cache
from card.models import Card


class CardMethodsRpcTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.card_params = {
            "card_number": "8600123412341234",
            "expire": "12/30",
            "phone": "998901234567",
            "status": "active",
            "balance": 1000.50
        }

    def rpc_call(self, method, params=None):
        """JSON-RPC request helper"""
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }
        response = self.client.post(
            "/api/cards/",
            data=json.dumps(body),
            content_type="application/json"
        )
        return json.loads(response.content)

    def test_card_add_success(self):
        resp = self.rpc_call("card.add", self.card_params)
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["message"], "Card added")
        self.assertEqual(
            resp["result"]["phone"].replace(" ", "").replace("+", ""),
            self.card_params["phone"]
        )

    def test_card_add_cache(self):
        # Birinchi marta RPC orqali qo‘shiladi
        self.rpc_call("card.add", self.card_params)
        # Ikkinchi marta ham shu param bilan yuborilsa cache ishlaydi
        resp = self.rpc_call("card.add", self.card_params)
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["message"], "Card added")

    def test_card_info_success(self):
        # Avval kartani qo‘shib olamiz
        self.rpc_call("card.add", self.card_params)
        resp = self.rpc_call("card.info", {
            "card_number": self.card_params["card_number"],
            "expire": self.card_params["expire"],
        })
        self.assertIn("result", resp)
        self.assertEqual(
            resp["result"]["phone"].replace(" ", "").replace("+", ""),
            self.card_params["phone"]
        )
        self.assertEqual(resp["result"]["card_status"], self.card_params["status"])

    def test_card_info_not_found(self):
        resp = self.rpc_call("card.info", {
            "card_number": "0000 1111 2222 3333",
            "expire": "11/29",
        })
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["message"], "Card not found")

    def test_card_import_csv(self):
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        df = pd.DataFrame([self.card_params])
        df.to_csv(tmp_file.name, index=False)
        tmp_file.close()

        resp = self.rpc_call("card.import", {"file_path": tmp_file.name})
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["created"], 1)

        os.unlink(tmp_file.name)

    def test_card_import_xlsx(self):
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        df = pd.DataFrame([self.card_params])
        df.to_excel(tmp_file.name, index=False, engine="openpyxl")
        tmp_file.close()

        resp = self.rpc_call("card.import", {"file_path": tmp_file.name})
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["created"], 1)

        os.unlink(tmp_file.name)
