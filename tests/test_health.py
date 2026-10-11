import http.client
import json
import os
import threading
import unittest

from ws19proof import SERVICE_NAME
from ws19proof.http_health import new_health_server


class HealthContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = new_health_server(port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()

    def request(self, path):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_health_is_json_and_self_identifying(self):
        status, headers, body = self.request("/healthz")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("application/json"))
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], SERVICE_NAME)
        self.assertEqual(data["pid"], os.getpid())
        self.assertEqual(len(data["instance_id"]), 32)
        self.assertTrue(data["started_at_utc"].endswith("+00:00"))

    def test_identity_stable_within_process(self):
        one = json.loads(self.request("/healthz")[2])
        two = json.loads(self.request("/healthz?probe=1")[2])
        self.assertEqual(one["pid"], two["pid"])
        self.assertEqual(one["instance_id"], two["instance_id"])

    def test_unknown_route_is_not_health(self):
        status, _, _ = self.request("/not-health")
        self.assertEqual(status, 404)

    def test_rejects_nonloopback_binding(self):
        with self.assertRaises(ValueError):
            new_health_server(host="0.0.0.0", port=0)


if __name__ == "__main__":
    unittest.main()
