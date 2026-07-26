import requests
from bs4 import BeautifulSoup

def continuous_cve_monitor():
    # Récupère les CVE les plus récentes
    url = 'https://nvd.nist.gov/vuln/full-listing'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    cves = []
    for row in soup.find_all('tr')[1:]:
        cols = row.find_all('td')
        if len(cols) > 0:
            cve_id = cols[1].text.strip()
            cve_description = cols[2].text.strip()
            cves.append({'id': cve_id, 'description': cve_description})
    return cves