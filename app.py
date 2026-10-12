"""TerraSignal: a small, explainable post-disaster damage assessment application."""

from __future__ import annotations


import csv
import io
import json
import os
import re
import tempfile
import threading
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from flask import Flask, Response, jsonify, render_template, request


CATEGORIES = {
    "Residential buildings": [r"houses?", r"homes?", r"dwellings?", r"residential buildings?"],
    "Roads & transport": [r"roads?", r"highways?", r"streets?", r"railway lines?"],
    "Bridges": [r"bridges?", r"culverts?"],
    "Power & electricity": [r"power lines?", r"electricity networks?", r"transformers?", r"power poles?", r"electricity infrastructure", r"power infrastructure"],
    "Water & sanitation": [r"water supply systems?", r"water supplies", r"pipelines?", r"wells?", r"sanitation systems?", r"sewers?", r"water infrastructure"],
    "Public facilities": [r"schools?", r"hospitals?", r"clinics?", r"shelters?", r"public facilities", r"community centers?"],
}

NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "dozen": 12,
}
UNIT_PATTERN = r"(?:kilometers?|kilometres?|km|meters?|metres?|m|miles?|bridges?|houses?|homes?|buildings?|roads?|schools?|wells?|units?|items?)"
SEVERITY_TERMS = [
    (r"\b(?:destroyed|collapsed|washed away|completely damaged)\b", "Severe"),
    (r"\b(?:severe|major|extensive|critical)\b", "Severe"),
    (r"\b(?:moderate|partially|partial)\b", "Moderate"),
    (r"\b(?:minor|slight|light)\b", "Minor"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _number_value(raw: str) -> float | int | None:
    raw = raw.strip().lower().replace(",", "")
    if raw in NUMBER_WORDS:
        return NUMBER_WORDS[raw]
    try:
        value = float(raw)
        return int(value) if value.is_integer() else value
    except ValueError:
        return None


def _normalize_unit(raw: str | None) -> str | None:
    if not raw:
        return "items"
    key = raw.lower().rstrip("s")
    if key in {"km", "kilometer", "kilometre"}:
        return "km"
    if key in {"m", "meter", "metre"}:
        return "m"
    if key in {"mile"}:
        return "miles"
    return "items"


def _extract_location(text: str) -> str | None:
    # Only use a place explicitly following a location preposition. The
    # conservative capitalization rule avoids turning arbitrary prose into a place.
    match = re.search(
        r"\b(?:in|at|near|around|from)\s+(?:the\s+)?"
        r"([A-Z][A-Za-z'-]*(?:\s+(?:[A-Z][A-Za-z'-]*|District|Village|Town|City|Block|Region|Valley)){0,4})",
        text,
    )
    return match.group(1).strip(" ,.;:") if match else None


def _extract_disaster_type(text: str) -> str | None:
    for label, pattern in [
        ("Flood", r"\bflood(?:ing|s)?\b"),
        ("Earthquake", r"\bearthquakes?\b"),
        ("Cyclone", r"\bcyclones?\b"),
        ("Landslide", r"\blandslides?\b"),
        ("Storm", r"\b(?:storms?|hurricanes?|typhoons?)\b"),
        ("Wildfire", r"\b(?:wildfires?|forest fires?)\b"),
        ("Drought", r"\bdroughts?\b"),
        ("El Niño-related extreme weather", r"\bel\s+ni[nñ]o\b"),
    ]:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return None


def _extract_severity(context: str) -> str | None:
    for pattern, label in SEVERITY_TERMS:
        if re.search(pattern, context, re.IGNORECASE):
            return label
    return None


def extract_report(text: str) -> dict:
    """Extract explicit report facts with keyword and regex rules; never invent quantities."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    damages: list[dict] = []
    occupied_spans: list[tuple[int, int]] = []
    for category, aliases in CATEGORIES.items():
        for alias in aliases:
            for match in re.finditer(rf"\b{alias}\b", cleaned, re.IGNORECASE):
                if any(match.start() < end and match.end() > start for start, end in occupied_spans):
                    continue
                occupied_spans.append((match.start(), match.end()))
                sentence_start = max(cleaned.rfind(mark, 0, match.start()) for mark in ".;!?") + 1
                before = cleaned[sentence_start:match.start()]
                quantity_match = re.search(
                    rf"(?P<number>\d[\d,]*(?:\.\d+)?|{'|'.join(NUMBER_WORDS)})"
                    rf"\s*(?P<unit>{UNIT_PATTERN})?\s*(?:of\s+)?(?:approximately\s+|about\s+|around\s+)?$",
                    before,
                    re.IGNORECASE,
                )
                quantity = _number_value(quantity_match.group("number")) if quantity_match else None
                unit = _normalize_unit(quantity_match.group("unit")) if quantity_match else None
                context_start = max(sentence_start, match.start() - 100)
                context_end = min(len(cleaned), match.end() + 100)
                context = cleaned[context_start:context_end]
                condition = next(
                    (word for word in ("destroyed", "collapsed", "damaged", "affected", "washed away")
                     if re.search(rf"\b{re.escape(word)}\b", context, re.IGNORECASE)),
                    None,
                )
                damages.append({
                    "category": category,
                    "asset": match.group(0),
                    "quantity": quantity,
                    "unit": unit,
                    "severity": _extract_severity(context),
                    "condition": condition,
                    "detail": context.strip(" ,.;"),
                })

    return {
        "location": _extract_location(cleaned),
        "disaster_type": _extract_disaster_type(cleaned),
        "damages": damages,
    }


def summarize(reports: list[dict]) -> dict:
    categories: Counter[str] = Counter()
    locations: Counter[str] = Counter()
    severities: Counter[str] = Counter()
    quantities: dict[str, Counter[str]] = defaultdict(Counter)
    quantified = 0
    for report in reports:
        extracted = report.get("extracted", {})
        location = extracted.get("location") or report.get("scene_location") or report.get("event_location") or "Unspecified"
        found = extracted.get("damages") or []
        if not found:
            locations[location] += 1
        for damage in found:
            categories[damage.get("category") or "Other infrastructure"] += 1
            locations[location] += 1
            severity = damage.get("severity")
            if severity:
                severities[severity] += 1
            quantity, unit = damage.get("quantity"), damage.get("unit")
            if isinstance(quantity, (int, float)) and unit:
                quantities[damage.get("category") or "Other infrastructure"][unit] += quantity
                quantified += 1
    return {
        "report_count": len(reports),
        "asset_mentions": sum(categories.values()),
        "quantified_mentions": quantified,
        "category_mentions": dict(categories),
        "location_mentions": dict(locations),
        "severity_mentions": dict(severities),
        "quantity_totals": {category: dict(units) for category, units in quantities.items()},
        "categories_affected": len(categories),
    }


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        JSON_STORE=str(Path(app.root_path) / "instance" / "damage_data.json"),
        MAX_CONTENT_LENGTH=1_000_000,
    )
    if test_config:
        app.config.update(test_config)
    lock = threading.RLock()

    def read_db() -> dict:
        path = Path(app.config["JSON_STORE"])
        if not path.exists():
            return {"events": [], "scenes": [], "reports": []}
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
            return {key: content.get(key, []) for key in ("events", "scenes", "reports")}
        except (OSError, json.JSONDecodeError):
            app.logger.exception("Could not read data store %s", path)
            return {"events": [], "scenes": [], "reports": []}

    def write_db(db: dict) -> None:
        path = Path(app.config["JSON_STORE"])
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(prefix="damage-data-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
                json.dump(db, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def load() -> dict:
        with lock:
            return read_db()

    def save(db: dict) -> None:
        with lock:
            write_db(db)

    def event_or_404(db: dict, event_id: str):
        event = next((row for row in db["events"] if row["id"] == event_id), None)
        return event

    def scenes_for(db: dict, event_id: str) -> list[dict]:
        return [row for row in db["scenes"] if row["event_id"] == event_id]

    def reports_for(db: dict, event_id: str, scene_id: str | None = None) -> list[dict]:
        return [row for row in db["reports"] if row["event_id"] == event_id and (scene_id is None or row.get("scene_id") == scene_id)]

    def enrich_reports(db: dict, reports: list[dict]) -> list[dict]:
        scenes = {row["id"]: row for row in db["scenes"]}
        events = {row["id"]: row for row in db["events"]}
        result = []
        for report in reports:
            item = dict(report)
            item["scene_name"] = scenes.get(report.get("scene_id"), {}).get("name")
            item["scene_location"] = scenes.get(report.get("scene_id"), {}).get("location")
            item["event_name"] = events.get(report["event_id"], {}).get("name")
            item["event_location"] = events.get(report["event_id"], {}).get("location")
            result.append(item)
        return result

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/api/events")
    def list_events():
        db = load()
        events = []
        for event in db["events"]:
            reports = enrich_reports(db, reports_for(db, event["id"]))
            events.append({**event, "summary": summarize(reports), "scene_count": len(scenes_for(db, event["id"]))})
        events.sort(key=lambda row: row.get("updated_at", ""), reverse=True)
        return jsonify(events)

    @app.post("/api/events")
    def create_event():
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name", "")).strip()
        if not name:
            return jsonify(error="Event name is required."), 400
        event = {
            "id": str(uuid4()), "name": name,
            "disaster_type": str(payload.get("disaster_type", "")).strip(),
            "location": str(payload.get("location", "")).strip(),
            "description": str(payload.get("description", "")).strip(),
            "start_date": str(payload.get("start_date", "")).strip(),
            "end_date": str(payload.get("end_date", "")).strip(),
            "created_at": now_iso(), "updated_at": now_iso(),
        }
        db = load()
        db["events"].append(event)
        save(db)
        return jsonify({**event, "summary": summarize([]), "scene_count": 0}), 201

    @app.patch("/api/events/<event_id>")
    def update_event(event_id: str):
        payload = request.get_json(silent=True) or {}
        db = load()
        event = event_or_404(db, event_id)
        if not event:
            return jsonify(error="Event not found."), 404
        for key in ("name", "disaster_type", "location", "description", "start_date", "end_date"):
            if key in payload:
                value = str(payload[key]).strip()
                if key == "name" and not value:
                    return jsonify(error="Event name is required."), 400
                event[key] = value
        event["updated_at"] = now_iso()
        save(db)
        return jsonify(event)

    @app.delete("/api/events/<event_id>")
    def delete_event(event_id: str):
        db = load()
        if not event_or_404(db, event_id):
            return jsonify(error="Event not found."), 404
        db["events"] = [row for row in db["events"] if row["id"] != event_id]
        scene_ids = {row["id"] for row in db["scenes"] if row["event_id"] == event_id}
        db["scenes"] = [row for row in db["scenes"] if row["event_id"] != event_id]
        db["reports"] = [row for row in db["reports"] if row["event_id"] != event_id and row.get("scene_id") not in scene_ids]
        save(db)
        return jsonify(ok=True)

    @app.get("/api/events/<event_id>/scenes")
    def list_scenes(event_id: str):
        db = load()
        if not event_or_404(db, event_id):
            return jsonify(error="Event not found."), 404
        rows = []
        for scene in scenes_for(db, event_id):
            reports = enrich_reports(db, reports_for(db, event_id, scene["id"]))
            rows.append({**scene, "summary": summarize(reports)})
        return jsonify(rows)

    @app.post("/api/events/<event_id>/scenes")
    def create_scene(event_id: str):
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name", "")).strip()
        if not name:
            return jsonify(error="Scene name is required."), 400
        db = load()
        if not event_or_404(db, event_id):
            return jsonify(error="Event not found."), 404
        scene = {
            "id": str(uuid4()), "event_id": event_id, "name": name,
            "location": str(payload.get("location", "")).strip(),
            "description": str(payload.get("description", "")).strip(),
            "created_at": now_iso(), "updated_at": now_iso(),
        }
        db["scenes"].append(scene)
        event_or_404(db, event_id)["updated_at"] = now_iso()
        save(db)
        return jsonify({**scene, "summary": summarize([])}), 201

    @app.patch("/api/events/<event_id>/scenes/<scene_id>")
    def update_scene(event_id: str, scene_id: str):
        payload = request.get_json(silent=True) or {}
        db = load()
        scene = next((row for row in db["scenes"] if row["id"] == scene_id and row["event_id"] == event_id), None)
        if not scene:
            return jsonify(error="Scene not found."), 404
        for key in ("name", "location", "description"):
            if key in payload:
                value = str(payload[key]).strip()
                if key == "name" and not value:
                    return jsonify(error="Scene name is required."), 400
                scene[key] = value
        scene["updated_at"] = now_iso()
        event_or_404(db, event_id)["updated_at"] = now_iso()
        save(db)
        return jsonify(scene)

    @app.delete("/api/events/<event_id>/scenes/<scene_id>")
    def delete_scene(event_id: str, scene_id: str):
        db = load()
        scene = next((row for row in db["scenes"] if row["id"] == scene_id and row["event_id"] == event_id), None)
        if not scene:
            return jsonify(error="Scene not found."), 404
        db["scenes"] = [row for row in db["scenes"] if row["id"] != scene_id]
        db["reports"] = [row for row in db["reports"] if row.get("scene_id") != scene_id]
        event_or_404(db, event_id)["updated_at"] = now_iso()
        save(db)
        return jsonify(ok=True)

    @app.get("/api/events/<event_id>/reports")
    def list_reports(event_id: str):
        db = load()
        if not event_or_404(db, event_id):
            return jsonify(error="Event not found."), 404
        scene_id = request.args.get("scene_id")
        if scene_id and not any(row["id"] == scene_id and row["event_id"] == event_id for row in db["scenes"]):
            return jsonify(error="Scene not found."), 404
        rows = enrich_reports(db, reports_for(db, event_id, scene_id))
        rows.sort(key=lambda row: row.get("created_at", ""), reverse=True)
        return jsonify(rows)

    @app.post("/api/events/<event_id>/reports")
    def create_report(event_id: str):
        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text", "")).strip()
        if not text:
            return jsonify(error="Report text is required."), 400
        if len(text) > 5000:
            return jsonify(error="Reports must be 5,000 characters or fewer."), 400
        db = load()
        event = event_or_404(db, event_id)
        if not event:
            return jsonify(error="Event not found."), 404
        scene_id = payload.get("scene_id") or None
        if scene_id and not any(row["id"] == scene_id and row["event_id"] == event_id for row in db["scenes"]):
            return jsonify(error="Selected scene does not belong to this event."), 400
        report = {
            "id": str(uuid4()), "event_id": event_id, "scene_id": scene_id,
            "original_text": text, "extracted": extract_report(text), "created_at": now_iso(),
        }
        db["reports"].append(report)
        event["updated_at"] = now_iso()
        save(db)
        enriched = enrich_reports(db, [report])[0]
        return jsonify(enriched), 201

    @app.patch("/api/events/<event_id>/reports/<report_id>")
    def update_report(event_id: str, report_id: str):
        payload = request.get_json(silent=True) or {}
        db = load()
        report = next((row for row in db["reports"] if row["id"] == report_id and row["event_id"] == event_id), None)
        if not report:
            return jsonify(error="Report not found."), 404
        if "extracted" in payload:
            extracted = payload["extracted"]
            if not isinstance(extracted, dict) or not isinstance(extracted.get("damages", []), list):
                return jsonify(error="Edited assessment is invalid."), 400
            damages = []
            for damage in extracted.get("damages", []):
                if not isinstance(damage, dict):
                    return jsonify(error="Each damage item must be an object."), 400
                qty = damage.get("quantity")
                if qty in ("", None):
                    qty = None
                else:
                    try:
                        qty = float(qty)
                        qty = int(qty) if qty.is_integer() else qty
                    except (TypeError, ValueError):
                        return jsonify(error="Quantities must be numbers or blank."), 400
                damages.append({
                    "category": str(damage.get("category", "Other infrastructure")),
                    "asset": str(damage.get("asset", "asset")),
                    "quantity": qty,
                    "unit": str(damage.get("unit", "items")) or None,
                    "severity": str(damage.get("severity", "")) or None,
                    "condition": str(damage.get("condition", "")) or None,
                    "detail": str(damage.get("detail", "")),
                })
            report["extracted"] = {
                "location": str(extracted.get("location", "")).strip() or None,
                "disaster_type": str(extracted.get("disaster_type", "")).strip() or None,
                "damages": damages,
            }
        event_or_404(db, event_id)["updated_at"] = now_iso()
        save(db)
        return jsonify(enrich_reports(db, [report])[0])

    @app.delete("/api/events/<event_id>/reports/<report_id>")
    def delete_report(event_id: str, report_id: str):
        db = load()
        before = len(db["reports"])
        db["reports"] = [row for row in db["reports"] if not (row["id"] == report_id and row["event_id"] == event_id)]
        if len(db["reports"]) == before:
            return jsonify(error="Report not found."), 404
        event_or_404(db, event_id)["updated_at"] = now_iso()
        save(db)
        return jsonify(ok=True)

    @app.get("/api/events/<event_id>/summary")
    def event_summary(event_id: str):
        db = load()
        event = event_or_404(db, event_id)
        if not event:
            return jsonify(error="Event not found."), 404
        scene_id = request.args.get("scene_id")
        if scene_id and not any(row["id"] == scene_id and row["event_id"] == event_id for row in db["scenes"]):
            return jsonify(error="Scene not found."), 404
        rows = enrich_reports(db, reports_for(db, event_id, scene_id))
        return jsonify(summarize(rows))

    def export_response(event_id: str, reports: list[dict], fmt: str, filename: str) -> Response:
        if fmt == "json":
            data = json.dumps(reports, ensure_ascii=False, indent=2)
            return Response(data, mimetype="application/json", headers={"Content-Disposition": f'attachment; filename="{filename}.json"'})
        if fmt != "csv":
            return Response(json.dumps({"error": "Format must be csv or json."}), status=400, mimetype="application/json")
        output = io.StringIO(newline="")
        fields = ["report_id", "event_id", "event_name", "scene_id", "scene_name", "submitted_at", "original_text", "location", "disaster_type", "category", "asset", "quantity", "unit", "severity", "condition", "detail"]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for report in reports:
            extracted = report.get("extracted", {})
            damages = extracted.get("damages") or [None]
            for damage in damages:
                writer.writerow({
                    "report_id": report.get("id"), "event_id": report.get("event_id"),
                    "event_name": report.get("event_name"), "scene_id": report.get("scene_id"),
                    "scene_name": report.get("scene_name"), "submitted_at": report.get("created_at"),
                    "original_text": report.get("original_text"), "location": extracted.get("location"),
                    "disaster_type": extracted.get("disaster_type"),
                    "category": damage.get("category") if damage else None,
                    "asset": damage.get("asset") if damage else None,
                    "quantity": damage.get("quantity") if damage else None,
                    "unit": damage.get("unit") if damage else None,
                    "severity": damage.get("severity") if damage else None,
                    "condition": damage.get("condition") if damage else None,
                    "detail": damage.get("detail") if damage else None,
                })
        return Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'})

    @app.get("/api/events/<event_id>/export")
    def export_event(event_id: str):
        db = load()
        event = event_or_404(db, event_id)
        if not event:
            return jsonify(error="Event not found."), 404
        rows = enrich_reports(db, reports_for(db, event_id))
        fmt = request.args.get("format", "csv").lower()
        slug = re.sub(r"[^a-z0-9]+", "-", event["name"].strip().lower()).strip("-") or "event"
        return export_response(event_id, rows, fmt, f"{slug}-reports")

    @app.get("/api/events/<event_id>/scenes/<scene_id>/export")
    def export_scene(event_id: str, scene_id: str):
        db = load()
        scene = next((row for row in db["scenes"] if row["id"] == scene_id and row["event_id"] == event_id), None)
        if not scene:
            return jsonify(error="Scene not found."), 404
        rows = enrich_reports(db, reports_for(db, event_id, scene_id))
        fmt = request.args.get("format", "csv").lower()
        slug = re.sub(r"[^a-z0-9]+", "-", scene["name"].strip().lower()).strip("-") or "scene"
        return export_response(event_id, rows, fmt, f"{slug}-reports")

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify(error="Request is too large."), 413

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
