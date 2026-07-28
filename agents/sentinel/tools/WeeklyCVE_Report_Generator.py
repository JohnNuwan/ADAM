
import requests
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

class WeeklyCVEReportGenerator:
    """
    Generates a weekly CVE report by fetching vulnerabilities from the NVD API
    published in the last 7 days.
    """

    NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    def __init__(self, results_per_page: int = 20):
        self.results_per_page = results_per_page

    def _get_last_week_date_range(self) -> tuple:
        """Returns (start_date, end_date) ISO strings for the past 7 days."""
        now = datetime.now(timezone.utc)
        end_date = now
        start_date = now - timedelta(days=7)
        return start_date.isoformat(), end_date.isoformat()

    def fetch_cves(self, start_date: str, end_date: str) -> List[Dict]:
        """
        Fetch CVEs from NVD API within the given date range.
        Returns list of CVE items.
        """
        params = {
            "pubStartDate": start_date,
            "pubEndDate": end_date,
            "resultsPerPage": self.results_per_page,
            "startIndex": 0
        }
        all_cves = []
        while True:
            try:
                response = requests.get(self.NVD_API_BASE, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                vulnerabilities = data.get("vulnerabilities", [])
                all_cves.extend(vulnerabilities)
                total_results = data.get("totalResults", 0)
                # Check if there are more pages
                if params["startIndex"] + self.results_per_page >= total_results:
                    break
                params["startIndex"] += self.results_per_page
            except requests.exceptions.RequestException as e:
                print(f"Error fetching CVEs: {e}")
                break
        return all_cves

    def generate_report(self, cves: List[Dict]) -> str:
        """
        Generate a human-readable report from a list of CVE items.
        Returns a string report.
        """
        if not cves:
            return "No CVEs found in the last week."

        report_lines = [
            "=" * 60,
            "WEEKLY CVE REPORT",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"Total CVEs found: {len(cves)}",
            "=" * 60,
            ""
        ]

        for idx, cve_item in enumerate(cves, 1):
            cve = cve_item.get("cve", {})
            cve_id = cve.get("id", "N/A")
            description = ""
            descriptions = cve.get("descriptions", [])
            for desc in descriptions:
                if desc.get("lang") == "en":
                    description = desc.get("value", "")
                    break
            # Truncate long descriptions
            if len(description) > 200:
                description = description[:197] + "..."
            published = cve.get("published", "N/A")
            severity = "N/A"
            metrics = cve.get("metrics", {})
            if "cvssMetricV31" in metrics:
                severity = metrics["cvssMetricV31"][0].get("cvssData", {}).get("baseSeverity", "N/A")
            elif "cvssMetricV30" in metrics:
                severity = metrics["cvssMetricV30"][0].get("cvssData", {}).get("baseSeverity", "N/A")
            elif "cvssMetricV2" in metrics:
                severity = metrics["cvssMetricV2"][0].get("baseSeverity", "N/A")

            report_lines.append(f"{idx}. {cve_id}")
            report_lines.append(f"   Published: {published}")
            report_lines.append(f"   Severity: {severity}")
            report_lines.append(f"   Description: {description}")
            report_lines.append("")

        return "\n".join(report_lines)

    def run(self) -> str:
        """Main method to generate the weekly CVE report."""
        start_date, end_date = self._get_last_week_date_range()
        print(f"Fetching CVEs from {start_date} to {end_date}...")
        cves = self.fetch_cves(start_date, end_date)
        report = self.generate_report(cves)
        return report

def main():
    generator = WeeklyCVEReportGenerator(results_per_page=50)
    report = generator.run()
    print(report)
    # Optionally save to file
    with open("weekly_cve_report.txt", "w", encoding="utf-8") as f:
        f.write(report)
    print("\nReport saved to weekly_cve_report.txt")

if __name__ == "__main__":
    main()
