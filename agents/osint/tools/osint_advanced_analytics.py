
import requests
from bs4 import BeautifulSoup
import re
import json

def fetch_web_content(url):
    response = requests.get(url)
    return response.text if response.status_code == 200 else None

def extract_links(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    links = [a['href'] for a in soup.find_all('a', href=True)]
    return links

def extract_emails(text):
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, text)
    return list(set(emails))

def analyze_url(url):
    content = fetch_web_content(url)
    if not content:
        return {}
    links = extract_links(content)
    emails = extract_emails(content)
    return {'links': links, 'emails': emails}

def save_results(results, filename='results.json'):
    with open(filename, 'w') as f:
        json.dump(results, f)

if __name__ == '__main__':
    url = 'https://example.com'
    analysis_results = analyze_url(url)
    save_results(analysis_results)
