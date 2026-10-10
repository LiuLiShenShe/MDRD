import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

from mdrd.common import now, write_json


def summarize(path):
    document = ET.parse(path).getroot()
    suites = list(document) if document.tag == "testsuites" else [document]
    if not suites or any(suite.tag != "testsuite" for suite in suites):
        raise ValueError(f"Expected JUnit testsuite data in {path}")
    counts = {"tests": 0, "failures": 0, "skipped": 0}
    for suite in suites:
        counts["tests"] += int(suite.attrib.get("tests", 0))
        counts["failures"] += int(suite.attrib.get("failures", 0)) + int(suite.attrib.get("errors", 0))
        counts["skipped"] += int(suite.attrib.get("skipped", 0))
    if counts["tests"] == 0:
        raise ValueError(f"No tests recorded in {path}")
    return counts


def main():
    parser = argparse.ArgumentParser(description="Summarize verified JUnit output, including testsuites roots")
    parser.add_argument("--unit", type=Path, required=True)
    parser.add_argument("--integration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    unit = summarize(args.unit)
    integration = summarize(args.integration)
    result = {
        "status": "PASSED" if not unit["failures"] and not integration["failures"] else "FAILED",
        "unit": unit,
        "integration": integration,
        "total_tests": unit["tests"] + integration["tests"],
        "failed": unit["failures"] + integration["failures"],
        "artifacts": [str(args.unit.resolve()), str(args.integration.resolve())],
        "summarized_at": now(),
    }
    write_json(args.output, result)
    print(f"{result['status']}: {result['total_tests']} tests, {result['failed']} failures")


if __name__ == "__main__":
    main()
