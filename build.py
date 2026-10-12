"""Create a clean, portable source build ZIP, excluding local runtime data."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "dist" / "terrasignal-v1.0.0.zip"
PROJECT_FILES = [
    ".gitignore",
    "README.md",
    "app.py",
    "build.py",
    "requirements.txt",
    "run_app.bat",
    "templates/index.html",
    "static/favicon.svg",
    "static/app.js",
    "static/styles.css",
    "tests/test_acceptance.py",
    "tests/TEST_CASES.md",
    "tests/test_app.py",
]


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prefix = "terrasignal"
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for relative in PROJECT_FILES:
            source = ROOT / relative
            archive.write(source, f"{prefix}/{relative}")
    print(f"Created {OUTPUT}")
    print(f"Included {len(PROJECT_FILES)} source and project files; local data is excluded.")


if __name__ == "__main__":
    main()
