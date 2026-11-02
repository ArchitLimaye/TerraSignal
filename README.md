# TerraSignal
### Post-Disaster Damage Assessment & Analytics Platform

TerraSignal is a web-based platform designed to organize, process, and analyze damage reports following natural disasters. It helps users manage disaster events, organize scenes, extract useful information from text-based reports, and visualize damage statistics through an interactive dashboard.

The platform combines explainable rule-based extraction with local NLP-based place-name recognition to make disaster report analysis easier to review and understand.

## Features

- **Disaster Event Management:** Create and manage individual disaster events.
- **Scene Organization:** Organize disaster events into separate scenes for structured assessment.
- **Damage Report Processing:** Process text-based reports to extract relevant damage information.
- **Local Place-Name Recognition:** Use spaCy's `en_core_web_sm` model to identify local place names mentioned in reports.
- **Explainable Information Extraction:** Apply explicit rules to identify damage categories, quantities, disaster types, and severity.
- **Interactive Analytics Dashboard:** Visualize damage statistics and report insights using interactive charts.
- **Data Export:** Export reports in CSV and JSON formats.
- **Local Data Storage:** Store application data using SQLite.
- **Dashboard Interface:** A refreshed dark-themed interface with rounded cards and amber and steel-blue accents.
- **Custom Branding:** Updated browser favicon and sidebar logo featuring a location and terrain signal icon.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| Flask | Web application framework |
| SQLite | Local database |
| spaCy | Local NLP-based place-name recognition |
| HTML, CSS, JavaScript | Frontend development |
| Chart.js | Interactive data visualization |

## How It Works

1. **Create a Disaster Event**  
   Add a disaster event to the platform.

2. **Organize Scenes**  
   Divide the event into separate scenes for better organization and assessment.

3. **Submit Damage Reports**  
   Enter text-based reports describing the observed damage.

4. **Extract Report Information**  
   TerraSignal uses spaCy's small English model for place-name recognition. Existing explainable rules extract damage categories, quantities, disaster types, and severity.

5. **Review Extracted Details**  
   Review and verify the extracted information before using it for further analysis.

6. **Analyze Damage Statistics**  
   Explore the collected data through interactive charts and dashboard visualizations.

7. **Export Reports**  
   Export the processed report data in CSV or JSON format.

## Getting Started

### Prerequisites

- Python 3.9 or later
- pip
- Git

### Installation

**1. Clone the repository**

```bash
git clone https://github.com/your-username/TerraSignal.git
cd TerraSignal
```

Replace `your-username` with the actual GitHub username or organization hosting the repository.

**2. Create a virtual environment**

```bash
python -m venv venv
```

**3. Activate the virtual environment**

Windows:

```bash
venv\Scripts\activate
```

Linux / macOS:

```bash
source venv/bin/activate
```

**4. Install dependencies**

```bash
pip install -r requirements.txt
```

The first installation downloads the spaCy English language model, `en_core_web_sm`, if it is configured in the project's dependencies.

**5. Run the application**

```bash
python app.py
```

**6. Open the application**

Visit the following URL in your browser:

```text
http://127.0.0.1:5000
```

## Report Processing

TerraSignal currently uses a combination of local NLP and explainable rule-based extraction.

- spaCy's `en_core_web_sm` model assists with place-name recognition.
- Explicit extraction rules identify damage categories, quantities, disaster types, and severity.
- Extracted report details should be reviewed and verified before being used for assessment or decision-making.

The application is designed to make extracted information easier to organize and analyze, rather than replace manual verification.

## Project Goal

The goal of TerraSignal is to make post-disaster damage reports easier to organize, review, and analyze through a simple and accessible web interface.

By combining structured event management, local NLP-based place recognition, explainable extraction rules, and interactive visualizations, TerraSignal aims to support a more organized approach to disaster damage assessment.

## Limitations

- Report processing currently relies on rule-based extraction.
- Place-name recognition depends on the capabilities of the spaCy English model.
- Extracted information may be incomplete or inaccurate and requires manual verification.
- TerraSignal is intended as an assessment and analytics aid, not a replacement for professional disaster response or field assessment.

## Future Improvements

- Improve damage information extraction.
- Add support for multilingual disaster reports.
- Integrate geospatial mapping for damage visualization.
- Introduce image-based damage assessment.
- Improve report validation and data quality checks.
- Expand analytics and reporting capabilities.

## License

This project is developed for educational and research purposes.
