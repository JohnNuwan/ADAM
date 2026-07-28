
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

def fetch_web_content(url):
    response = requests.get(url)
    return response.text if response.status else None

def parse_techniques(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    techniques = []
    for technique in soup.find_all('div', class_='technique'):
        name = technique.find('h2').text
        date_str = technique.find('span', class_='date').text
        date = datetime.strptime(date_str, '%Y-%m-%d')
        lessons = [lesson.text for lesson in technique.find_all('li')]
        techniques.append({'name': name, 'date': date, 'lessons': lessons})
    return techniques

def filter_new_techniques(techniques, last_check_date):
    return [t for t in techniques if t['date'] > last_check_date]

def main():
    url = "https://example.com/osint-innovations"
    last_check_date = datetime.now()  # This should be saved and restored between runs.
    html_content = fetch_web_content(url)
    if html_content:
        techniques = parse_techniques(html_content)
        new_techniques = filter_new_techniques(techniques, last_check_date)
        for tech in new_techniques:
            print(f"New Technique Detected: {tech['name']} - Lessons Learned: {tech['lessons']}")

if __name__ == '__main__':
    main()
