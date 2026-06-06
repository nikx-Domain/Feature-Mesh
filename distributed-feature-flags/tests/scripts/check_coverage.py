import xml.etree.ElementTree as ET
import sys
import os

def check_coverage(xml_path="coverage.xml"):
    if not os.path.exists(xml_path):
        print(f"Error: {xml_path} not found. Run pytest --cov --cov-report=xml first.")
        sys.exit(1)

    tree = ET.parse(xml_path)
    root = tree.getroot()

    thresholds = {
        "app.domain.evaluation": 0.90,
        "app.infrastructure.cache": 0.85,
        "app.infrastructure.kafka": 0.85,
        "sdk": 0.85
    }

    failed = False

    for package in root.findall(".//package"):
        name = package.get("name")
        for target_pkg, threshold in thresholds.items():
            if name.startswith(target_pkg):
                line_rate = float(package.get("line-rate"))
                if line_rate < threshold:
                    print(f"❌ FAIL: {name} coverage is {line_rate:.1%}. Required: {threshold:.1%}")
                    failed = True
                else:
                    print(f"✅ PASS: {name} coverage is {line_rate:.1%}. Required: {threshold:.1%}")

    overall_line_rate = float(root.get("line-rate"))
    print(f"Overall Coverage: {overall_line_rate:.1%}")

    if failed:
        print("\nCI Gate Failed: One or more coverage thresholds were not met.")
        sys.exit(1)
    else:
        print("\nCI Gate Passed: All coverage thresholds met.")
        sys.exit(0)

if __name__ == "__main__":
    xml_file = sys.argv[1] if len(sys.argv) > 1 else "coverage.xml"
    check_coverage(xml_file)
