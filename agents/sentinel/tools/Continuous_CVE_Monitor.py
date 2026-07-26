
import requests
from datetime import datetime, timedelta

def fetch_latest_cves(api_url):
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.json()
    else:
        return None

def filter_new_cves(all_cves, last_check_time):
    new_cves = []
    for cve in all_cves:
        published_date = datetime.strptime(cve['publishedDate'], '%Y-%m-%dT%H:%M:%SZ')
        if published_date > last_check_time:
            new_cves.append(cve)
    return new_cves

def monitor_cves(api_url, interval_minutes=15):
    last_check_time = datetime.now() - timedelta(days=1)  # Start with a date far back enough
    while True:
        print(f"Checking for new CVEs at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        cves = fetch_latest_cves(api_url)
        if cves:
            new_cves = filter_new_cves(cves, last_check_time)
            if new_cves:
                print("New CVEs found:")
                for cve in new_cves:
                    print(f"- {cve['id']} : {cve['summary']}")
            else:
                print("No new CVEs found.")
            last_check_time = datetime.now()
        else:
            print("Failed to fetch CVEs.")
        time.sleep(interval_minutes * 60)

if __name__ == '__main__':
    import time
    API_URL = "https://services.nvd.nist.gov/rest/json/cves/1.0"
    monitor_cves(API_URL)
