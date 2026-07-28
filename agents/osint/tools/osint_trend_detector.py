
import requests
from bs4 import BeautifulSoup
import re
from collections import Counter

class OSINTTrendDetector:
    def __init__(self):
        self.sources = [
            "https://www.osinttechniques.com/",
            "https://www.intelligenceonline.com/",
            "https://www.opensourceintel.com/"
        ]
        self.keywords = ["OSINT", "intelligence", "data", "trends", "tools", "techniques"]

    def fetch_content(self, url):
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        else:
            return ""

    def extract_text(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text()
        return text

    def find_keywords(self, text):
        words = re.findall(r'\w+', text.lower())
        keyword_counts = Counter([word for word in words if word in self.keywords])
        return keyword_counts

    def detect_trends(self):
        trends = {}
        for source in self.sources:
            content = self.fetch_content(source)
            text = self.extract_text(content)
            keyword_counts = self.find_keywords(text)
            trends[source] = keyword_counts
        return trends

if __name__ == "__main__":
    detector = OSINTTrendDetector()
    trends = detector.detect_trends()
    for source, counts in trends.items():
        print(f"Trends from {source}:")
        for keyword, count in counts.items():
            print(f"Keyword '{keyword}': {count}")
