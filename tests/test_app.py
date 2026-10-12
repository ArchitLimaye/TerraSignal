import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from app import create_app, extract_report


class ExtractionTests(unittest.TestCase):
    def test_extracts_only_explicit_report_details(self):
        result = extract_report(
            "Heavy flooding in Village A has damaged 25 houses, two bridges, "
            "and approximately 3 km of road. The water supply system is partially damaged."
        )
        self.assertEqual(result["location"], "Village A")
        self.assertEqual(result["disaster_type"], "Flood")
        by_asset = {damage["category"]: damage for damage in result["damages"]}
        self.assertEqual(by_asset["Residential buildings"]["quantity"], 25)
        self.assertEqual(by_asset["Bridges"]["quantity"], 2)
        self.assertEqual(by_asset["Roads & transport"]["quantity"], 3)
        self.assertEqual(by_asset["Roads & transport"]["unit"], "km")
        self.assertEqual(by_asset["Water & sanitation"]["quantity"], None)
        self.assertEqual(by_asset["Water & sanitation"]["severity"], "Moderate")

    def test_missing_quantity_and_severity_stay_unknown(self):
        result = extract_report("Several homes and one bridge were affected near Ridge Camp.")
        self.assertEqual(result["location"], "Ridge Camp")
        houses = next(row for row in result["damages"] if row["category"] == "Residential buildings")
        self.assertIsNone(houses["quantity"])
        self.assertIsNone(houses["severity"])


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "records.json"
        self.app = create_app({"TESTING": True, "JSON_STORE": str(self.path)})
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def create_event(self, name, location):
        response = self.client.post("/api/events", json={"name": name, "location": location, "disaster_type": "Flood"})
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()

    def create_scene(self, event_id, name, location):
        response = self.client.post(f"/api/events/{event_id}/scenes", json={"name": name, "location": location})
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()

    def submit(self, event_id, text, scene_id=None):
        response = self.client.post(f"/api/events/{event_id}/reports", json={"text": text, "scene_id": scene_id})
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()

    def test_event_and_scene_data_are_isolated_in_summaries_and_exports(self):
        first = self.create_event("Ladakh Floods", "Ladakh")
        second = self.create_event("Himachal Floods", "Himachal Pradesh")
        mandi = self.create_scene(second["id"], "Mandi District", "Mandi")
        self.submit(first["id"], "Flooding in Leh damaged 5 houses.")
        self.submit(second["id"], "Flooding in Mandi damaged 3 bridges.", mandi["id"])
        self.submit(second["id"], "Road damage was reported in Kullu.")

        first_reports = self.client.get(f"/api/events/{first['id']}/reports").get_json()
        scene_reports = self.client.get(f"/api/events/{second['id']}/reports?scene_id={mandi['id']}").get_json()
        scene_summary = self.client.get(f"/api/events/{second['id']}/summary?scene_id={mandi['id']}").get_json()
        self.assertEqual(len(first_reports), 1)
        self.assertEqual(len(scene_reports), 1)
        self.assertEqual(scene_summary["asset_mentions"], 1)

        event_export = self.client.get(f"/api/events/{second['id']}/export?format=json").get_json()
        scene_export = self.client.get(f"/api/events/{second['id']}/scenes/{mandi['id']}/export?format=json").get_json()
        self.assertEqual(len(event_export), 2)
        self.assertEqual(len(scene_export), 1)
        self.assertTrue(all(row["event_id"] == second["id"] for row in event_export))
        self.assertTrue(all(row["scene_id"] == mandi["id"] for row in scene_export))

        csv_response = self.client.get(f"/api/events/{second['id']}/scenes/{mandi['id']}/export?format=csv")
        rows = list(csv.DictReader(io.StringIO(csv_response.get_data(as_text=True).lstrip("\ufeff"))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["scene_id"], mandi["id"])

    def test_scene_delete_cascades_its_reports_but_keeps_event_reports(self):
        event = self.create_event("Coastal Flood", "Coast")
        scene = self.create_scene(event["id"], "North Zone", "North")
        self.submit(event["id"], "Two bridges were damaged.", scene["id"])
        self.submit(event["id"], "One school was damaged.")
        response = self.client.delete(f"/api/events/{event['id']}/scenes/{scene['id']}")
        self.assertEqual(response.status_code, 200)
        reports = self.client.get(f"/api/events/{event['id']}/reports").get_json()
        self.assertEqual(len(reports), 1)
        self.assertIsNone(reports[0]["scene_id"])

    def test_report_assessment_can_be_corrected(self):
        event = self.create_event("Test Flood", "North")
        report = self.submit(event["id"], "Flooding damaged some houses.")
        response = self.client.patch(
            f"/api/events/{event['id']}/reports/{report['id']}",
            json={"extracted": {"location": "Mandi", "disaster_type": "Flood", "damages": [
                {"category": "Residential buildings", "asset": "houses", "quantity": "8", "unit": "items", "severity": "Minor"}
            ]}},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["extracted"]["location"], "Mandi")
        self.assertEqual(response.get_json()["extracted"]["damages"][0]["quantity"], 8)

    def test_rejects_cross_event_scene_assignment_and_empty_names(self):
        one = self.create_event("One", "North")
        two = self.create_event("Two", "South")
        scene = self.create_scene(one["id"], "North District", "North")
        response = self.client.post(f"/api/events/{two['id']}/reports", json={"text": "A bridge was damaged", "scene_id": scene["id"]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post("/api/events", json={"name": " "}).status_code, 400)

    def test_event_delete_removes_all_child_data(self):
        event = self.create_event("Temporary event", "East")
        scene = self.create_scene(event["id"], "Scene 1", "East")
        self.submit(event["id"], "Three houses damaged.", scene["id"])
        self.assertEqual(self.client.delete(f"/api/events/{event['id']}").status_code, 200)
        self.assertEqual(self.client.get("/api/events").get_json(), [])
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(saved, {"events": [], "scenes": [], "reports": []})


if __name__ == "__main__":
    unittest.main()
