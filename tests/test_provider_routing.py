import os
import sys
import json
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import init_db, SessionLocal, engine, Base
from backend.database.models import AuditLogModel, BusInventoryModel, BookingModel
from backend.providers.base import BaseTravelProvider
from backend.providers.router import ProviderRouter, ProviderHealth

class DummyFailProvider(BaseTravelProvider):
    def __init__(self):
        self.fail_count = 0

    @property
    def name(self) -> str:
        return "DummyFailProvider"

    def search_buses(self, origin: str, destination: str, travel_date: str) -> list:
        self.fail_count += 1
        raise ConnectionError("Network unreachable")

    def hold_seat(self, bus_id: int, seat_number: str, passenger_name: str, passenger_email: str, session_id: str) -> dict:
        return {"success": False, "error": "Timeout"}

    def confirm_booking(self, booking_id: int) -> dict:
        return {"success": False, "error": "Timeout"}

    def cancel_booking(self, booking_id: int, session_id: str) -> dict:
        return {"success": False, "error": "Timeout"}


class TestProviderRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        init_db()

    def setUp(self):
        self.db = SessionLocal()
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        
        # Seed test data
        seats = json.dumps(["1A", "1B", "2A", "2B"])
        self.bus1 = BusInventoryModel(
            operator_name="VRL Travels",
            bus_type="Sleeper",
            departure_time="22:00",
            arrival_time="06:00",
            duration="8h",
            origin="Bangalore",
            destination="Hyderabad",
            fare=1000.0,
            rating=4.5,
            available_seats=4,
            seat_layout_raw=seats
        )
        self.db.add(self.bus1)
        self.db.commit()
        
        self.router = ProviderRouter()
        self.router.preferred_provider_name = "mockbusprovider"
        for name_key, health in self.router.health_records.items():
            health.status = "HEALTHY"
            health.consecutive_failures = 0

    def tearDown(self):
        self.db.close()

    def test_preferred_routing_success(self):
        provider = self.router.get_active_provider()
        self.assertEqual(provider.name, "MockBusProvider")
        
        res = self.router.search_buses("Bangalore", "Hyderabad", "2026-06-28")
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0]["operator_name"], "VRL Travels")
        self.assertEqual(self.router.health_records["mockbusprovider"].status, "HEALTHY")

    def test_provider_failover(self):
        fail_provider = DummyFailProvider()
        self.router.register_provider(fail_provider, max_failures=2)
        self.router.preferred_provider_name = "dummyfailprovider"
        
        self.assertEqual(self.router.get_active_provider().name, "DummyFailProvider")
        
        # Executes search -> fails -> router immediately retries search via MockBusProvider fallback
        res = self.router.search_buses("Bangalore", "Hyderabad", "2026-06-28")
        
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0]["operator_name"], "VRL Travels")
        
        dummy_health = self.router.health_records["dummyfailprovider"]
        self.assertEqual(dummy_health.consecutive_failures, 1)
        self.assertEqual(dummy_health.status, "HEALTHY")
        
        # Force a second failure via hold_seat to trip status to UNHEALTHY
        try:
            self.router.hold_seat(self.bus1.id, "1A", "Test", "test@test.com", "sess_test")
        except Exception:
            pass
            
        self.assertEqual(dummy_health.status, "UNHEALTHY")
        
        # Preferred is unhealthy, active provider should fall back to another healthy provider
        active = self.router.get_active_provider()
        self.assertNotEqual(active.name, "DummyFailProvider")
        self.assertIn(active.name, ["MockBusProvider", "BackupBusProvider"])

    def test_audit_logging(self):
        self.db.query(AuditLogModel).filter(AuditLogModel.agent_name == "ProviderRouter").delete()
        self.db.commit()
        
        self.router.search_buses("Bangalore", "Hyderabad", "2026-06-28")
        
        logs = self.db.query(AuditLogModel).filter(AuditLogModel.agent_name == "ProviderRouter").all()
        self.assertTrue(len(logs) > 0)
        self.assertIn("MockBusProvider", logs[0].reasoning_summary)
