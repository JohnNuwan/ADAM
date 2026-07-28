
import requests
from bs4 import BeautifulSoup
import time

class AcademicWatch:
    def __init__(self):
        self.base_url = "https://arxiv.org"
        self.query_url = f"{self.base_url}/list/cs.AI/recent"
        self.publications = []

    def fetch_publications(self):
        response = requests.get(self.query_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            titles = [a.text for a in soup.select(".list-title > a")]
            abstracts = [a.text.strip() for a in soup.select(".mathjax")]
            links = [self.base_url + a['href'] for a in soup.select(".list-title > a")]
            self.publications = [{'title': title, 'abstract': abstract, 'link': link} for title, abstract, link in zip(titles, abstracts, links)]
        else:
            print("Failed to fetch data")

    def filter_publications(self, keywords):
        filtered_publications = []
        for pub in self.publications:
            if any(keyword.lower() in pub['title'].lower() or keyword.lower() in pub['abstract'].lower() for keyword in keywords):
                filtered_publications.append(pub)
        return filtered_publications

    def monitor(self, keywords, interval=3600):
        while True:
            self.fetch_publications()
            relevant_publications = self.filter_publications(keywords)
            for pub in relevant_publications:
                print(f"Title: {pub['title']}\nAbstract: {pub['abstract']}\nLink: {pub['link']}\n")
            time.sleep(interval)

if __name__ == "__main__":
    watch_tool = AcademicWatch()
    keywords = ["AGI", "auto-improvement"]
    watch_tool.monitor(keywords)
