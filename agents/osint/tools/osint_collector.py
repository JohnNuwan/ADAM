import requests
from bs4 import BeautifulSoup

def collect_osint(target, sources):
    results = []
    for source in sources:
        if source == 'LinkedIn':
            url = f'https://www.linkedin.com/in/{target}/'
        elif source == 'Twitter':
            url = f'https://twitter.com/{target}'
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Collect relevant data
        results.append({source: soup.title.string})
    return results
# Example usage
results = collect_osint('EVA', ['LinkedIn', 'Twitter'])
print(results)