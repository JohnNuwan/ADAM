import requests
from bs4 import BeautifulSoup

def scrape_emails(target):
    results = []
    # Define the search URL
    url = f'https://search.example.com?q={target}+email'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    # Find all email addresses
    emails = soup.find_all('a', href=True)
    for email in emails:
        if '@' in email['href'] and target.lower() in email['href'].lower():
            results.append(email['href'])
    return results
# Example usage
emails = scrape_emails('EVA')
print(emails)