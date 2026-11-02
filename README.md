# TerraSignal
### Post-Disaster Damage Assessment & Analytics Platform

TerraSignal is a web application that helps organize and analyze damage reports after natural disasters. It processes text-based reports, manages disaster events and scenes, and displays damage statistics through interactive charts.

## Features

- Create and manage disaster events.
- Organize events into separate scenes.
- Process text-based damage reports with a local NLP model and explainable extraction rules.
- Visualize damage statistics using charts.
- Export reports in CSV and JSON formats.
- Store data using SQLite.

## Tech Stack

- Python and Flask
- SQLite
- HTML, CSS, and JavaScript
- Chart.js

## Getting Started

1. Clone this repository.
2. Create and activate a virtual environment.
3. Install the dependencies:

```bash
pip install -r requirements.txt
```

4. Run the application:

```bash
python app.py
```

5. Open `http://127.0.0.1:5000` in your browser.

The first dependency installation downloads the spaCy model. After installation, report processing runs locally. The model assists with place-name recognition; the app's explicit rules continue to extract damage categories, quantities, and severity for review.

## Project Goal

The goal of TerraSignal is to make disaster damage reports easier to organize, review, and analyze through a simple web interface.

*Note: The current report processing uses rule-based extraction, so results may require manual verification.*
