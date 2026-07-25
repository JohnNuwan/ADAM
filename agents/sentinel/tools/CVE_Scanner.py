import requests
from bs4 import BeautifulSoup

def get_last_cve():
    url = 'https://cve.mitre.org/data/refs/source/CVE/CVE-List.html'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    cves = []
    for link in soup.find_all('a', href=True):
        if link['href'].startswith('/data/cve/cve-'):
            cves.append(link['href'][14:])
    return cves[:3]

last_cve = get_last_cve()
print(last_cve)