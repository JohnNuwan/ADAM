
import requests
from bs4 import BeautifulSoup
import re

class DomainAnalysisTool:
    def __init__(self, domain_url):
        self.domain_url = domain_url
        self.components = []

    def fetch_page(self):
        response = requests.get(self.domain_url)
        if response.status_code == 200:
            return response.text
        else:
            raise Exception(f"Failed to fetch page: {response.status_code}")

    def extract_links(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True)]
        return links

    def identify_components(self, links):
        component_patterns = [
            {'name': 'Login Page', 'pattern': r'/login'},
            {'name': 'Register Page', 'pattern': r'/register'},
            {'name': 'Dashboard', 'pattern': r'/dashboard'},
            # Add more patterns as needed
        ]
        
        for link in links:
            for pattern in component_patterns:
                if re.search(pattern['pattern'], link):
                    self.components.append(pattern['name'])
        
    def analyze_domain(self):
        page_content = self.fetch_page()
        links = self.extract_links(page_content)
        self.identify_components(links)

    def get_results(self):
        self.analyze_domain()
        return self.components

# Example usage
if __name__ == "__main__":
    tool = DomainAnalysisTool("https://example.com")
    results = tool.get_results()
    print(results)
