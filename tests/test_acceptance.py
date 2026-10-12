"""Ten isolated acceptance cases for the assessor website and API."""

import csv
import io
import tempfile
import unittest
from pathlib import Path

from app import create_app


class WebsiteAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "JSON_STORE": str(Path(self.temp.name) / "acceptance-data.json"),
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def event(self, name="Test Flood", location="North Region"):
        response = self.client.post("/api/events", json={"name": name, "location": location, "disaster_type": "Flood"})
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()

    def scene(self, event_id, name, location="North District"):
        response = self.client.post(f"/api/events/{event_id}/scenes", json={"name": name, "location": location})
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()

    def report(self, event_id, text, scene_id=None):
        response = self.client.post(f"/api/events/{event_id}/reports", json={"text": text, "scene_id": scene_id})
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()

    def test_01_homepage_and_frontend_assets_load(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"TerraSignal", page.data)
        self.assertIn(b"mainView", page.data)
        script = self.client.get("/static/app.js")
        stylesheet = self.client.get("/static/styles.css")
        icon = self.client.get("/static/favicon.svg")
        self.assertEqual(script.status_code, 200)
        self.assertEqual(stylesheet.status_code, 200)
        self.assertEqual(icon.status_code, 200)
        self.assertIn(b"Damage mentions by reported location", script.data)
        self.assertNotIn(b"Reports by reported location", script.data)
        script.close()
        stylesheet.close()
        icon.close()

    def test_02_health_endpoint_reports_ready(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_03_event_validation_create_edit_and_list(self):
        self.assertEqual(self.client.post("/api/events", json={"name": "  "}).status_code, 400)
        event = self.event()
        update = self.client.patch(f"/api/events/{event['id']}", json={"name": "North Flood 2026", "location": "Mandi"})
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.get_json()["name"], "North Flood 2026")
        listed = self.client.get("/api/events").get_json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["location"], "Mandi")

    def test_04_scene_belongs_to_one_event_and_rejects_foreign_assignment(self):
        event_a, event_b = self.event("Event A"), self.event("Event B", "South")
        scene_a = self.scene(event_a["id"], "Mandi")
        self.assertEqual(self.client.get(f"/api/events/{event_b['id']}/scenes").get_json(), [])
        response = self.client.post(f"/api/events/{event_b['id']}/reports", json={"text": "A bridge is damaged", "scene_id": scene_a["id"]})
        self.assertEqual(response.status_code, 400)

    def test_05_report_extraction_keeps_explicit_quantities_and_unknowns(self):
        event = self.event()
        report = self.report(event["id"], "Severe flooding in Mandi damaged 12 houses and two bridges; roads were affected.")
        extracted = report["extracted"]
        self.assertEqual(extracted["location"], "Mandi")
        self.assertEqual(extracted["disaster_type"], "Flood")
        damages = {row["category"]: row for row in extracted["damages"]}
        self.assertEqual(damages["Residential buildings"]["quantity"], 12)
        self.assertEqual(damages["Bridges"]["quantity"], 2)
        self.assertEqual(damages["Residential buildings"]["severity"], "Severe")
        self.assertIsNone(damages["Roads & transport"]["quantity"])

    def test_06_event_and_scene_summaries_aggregate_without_mixing_events(self):
        event_a, event_b = self.event("Event A"), self.event("Event B", "South")
        scene_a, scene_b = self.scene(event_a["id"], "Mandi"), self.scene(event_a["id"], "Kullu", "Kullu")
        self.report(event_a["id"], "Five houses and 2 bridges damaged in Mandi.", scene_a["id"])
        self.report(event_a["id"], "One road damaged in Kullu.", scene_b["id"])
        self.report(event_b["id"], "Four houses damaged in Leh.")
        event_summary = self.client.get(f"/api/events/{event_a['id']}/summary").get_json()
        scene_summary = self.client.get(f"/api/events/{event_a['id']}/summary?scene_id={scene_a['id']}").get_json()
        self.assertEqual(event_summary["report_count"], 2)
        self.assertEqual(event_summary["asset_mentions"], 3)
        self.assertEqual(scene_summary["report_count"], 1)
        self.assertEqual(scene_summary["asset_mentions"], 2)
        self.assertNotIn("Event B", event_summary["location_mentions"])
        self.assertEqual(event_summary["quantity_totals"]["Residential buildings"]["items"], 5)

    def test_07_assessment_correction_updates_dashboard_totals(self):
        event = self.event()
        report = self.report(event["id"], "Several houses were affected.")
        patch = self.client.patch(f"/api/events/{event['id']}/reports/{report['id']}", json={
            "extracted": {"location": "Mandi", "disaster_type": "Flood", "damages": [
                {"category": "Residential buildings", "asset": "houses", "quantity": "7", "unit": "items", "severity": "Moderate"}
            ]},
        })
        self.assertEqual(patch.status_code, 200)
        summary = self.client.get(f"/api/events/{event['id']}/summary").get_json()
        self.assertEqual(summary["quantity_totals"]["Residential buildings"]["items"], 7)
        self.assertEqual(summary["severity_mentions"]["Moderate"], 1)

    def test_08_json_and_csv_exports_are_scoped_and_readable(self):
        event = self.event()
        scene = self.scene(event["id"], "Mandi")
        self.report(event["id"], "Three houses damaged.", scene["id"])
        self.report(event["id"], "Road was damaged.")
        scene_json = self.client.get(f"/api/events/{event['id']}/scenes/{scene['id']}/export?format=json").get_json()
        event_json = self.client.get(f"/api/events/{event['id']}/export?format=json").get_json()
        self.assertEqual(len(scene_json), 1)
        self.assertEqual(len(event_json), 2)
        self.assertEqual(scene_json[0]["scene_id"], scene["id"])
        self.assertEqual(scene_json[0]["original_text"], "Three houses damaged.")
        response = self.client.get(f"/api/events/{event['id']}/scenes/{scene['id']}/export?format=csv")
        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True).lstrip("\ufeff"))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["scene_name"], "Mandi")

    def test_09_scene_delete_removes_its_reports_but_preserves_other_reports(self):
        event = self.event()
        scene_a, scene_b = self.scene(event["id"], "Mandi"), self.scene(event["id"], "Kullu", "Kullu")
        self.report(event["id"], "Two bridges damaged.", scene_a["id"])
        self.report(event["id"], "One house damaged.", scene_b["id"])
        self.report(event["id"], "Road damage event-wide.")
        response = self.client.delete(f"/api/events/{event['id']}/scenes/{scene_a['id']}")
        self.assertEqual(response.status_code, 200)
        reports = self.client.get(f"/api/events/{event['id']}/reports").get_json()
        self.assertEqual(len(reports), 2)
        self.assertNotIn(scene_a["id"], [row["scene_id"] for row in reports])
        self.assertEqual(len(self.client.get(f"/api/events/{event['id']}/scenes").get_json()), 1)

    def test_10_event_delete_removes_child_records_only_for_that_event(self):
        event_a, event_b = self.event("Event A"), self.event("Event B", "South")
        scene_a = self.scene(event_a["id"], "A-scene")
        self.scene(event_b["id"], "B-scene", "South")
        self.report(event_a["id"], "A report with one house.", scene_a["id"])
        self.report(event_b["id"], "B report with one bridge.")
        response = self.client.delete(f"/api/events/{event_a['id']}")
        self.assertEqual(response.status_code, 200)
        remaining = self.client.get("/api/events").get_json()
        self.assertEqual([row["id"] for row in remaining], [event_b["id"]])
        self.assertEqual(len(self.client.get(f"/api/events/{event_b['id']}/reports").get_json()), 1)
        self.assertEqual(len(self.client.get(f"/api/events/{event_b['id']}/scenes").get_json()), 1)


if __name__ == "__main__":
    unittest.main()
