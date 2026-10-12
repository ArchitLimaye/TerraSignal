# Ten website acceptance cases

Run these cases against an isolated temporary JSON store:

```powershell
python -m unittest discover -s tests -p test_acceptance.py -v
```

| # | Case | Expected result | Last run |
|---|---|---|---|
| 1 | Homepage and frontend assets | Home page, JavaScript, CSS, and icon respond successfully; the location chart label matches its data. | Pass |
| 2 | Health check | `/api/health` returns `200` and `{"status":"ok"}`. | Pass |
| 3 | Event validation and editing | Blank event names are rejected; a valid event can be created, edited, and listed with the updated details. | Pass |
| 4 | Scene ownership | Scenes are scoped to their parent event; another event cannot attach a report to that scene. | Pass |
| 5 | Report extraction | Explicit place, disaster, quantities, and severity are extracted; a missing quantity remains unknown. | Pass |
| 6 | Event and scene summaries | Scene totals roll into their event; selected-scene summaries stay scoped; other events do not leak in. | Pass |
| 7 | Assessment correction | Corrected location, quantity, and severity persist and update dashboard totals. | Pass |
| 8 | CSV and JSON exports | Exports include the original report and identifiers; scene exports contain only that scene while event exports include all event reports. | Pass |
| 9 | Scene deletion | Deleting a scene removes its reports while preserving event-wide and other-scene reports. | Pass |
| 10 | Event deletion | Deleting an event removes its scenes and reports but leaves unrelated events intact. | Pass |

The ten cases above are API integration tests with a temporary data store. A separate browser walkthrough also exercised event creation, scene creation, report submission, assessment correction, scene-level totals, and the dashboard label. The live local site loaded with no browser console errors. The user's local workspace data was not used by the automated test suite.

Cross-browser compatibility, assistive-technology behavior, performance/load, and production hosting configuration are outside this check.
