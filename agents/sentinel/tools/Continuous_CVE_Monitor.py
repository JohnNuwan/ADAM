
import requests
from bs4 import BeautifulSoup
import time

def fetch_cve_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to fetch data from {url}")

def parse_cve_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    cves = []
    # Example parsing logic, adjust according to actual HTML structure
    for entry in soup.find_all('entry'):
        cve_id = entry.cveid.string
        summary = entry.summary.string
        cves.append({'cve_id': cve_id, 'summary': summary})
    return cves

def monitor_cves(url, interval=3600):
    last_known_cves = set()
    while True:
        try:
            html_content = fetch_cve_data(url)
            current_cves = parse_cve_data(html_content)
            new_cves = [cve for cve in current_cves if cve['cve_id'] not in last_known_cves]
            if new_cves:
                print("New CVEs found:")
                for cve in new_cves:
                    print(f"CVE ID: {cve['cve_id']}, Summary: {cve['summary']}")
                last_known_cves.update([cve['cve_id'] for cve in current_cves])
            time.sleep(interval)
        except Exception as e:
            print(f"An error occurred: {e}")
            time.sleep(interval)

if __name__ == '__main__':
    url = "https://www.example.com/cve-feed.xml"  # Replace with the actual URL of the CVE feed
    monitor_cves(url)
