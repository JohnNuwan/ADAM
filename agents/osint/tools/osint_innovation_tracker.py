import requests
from bs4 import BeautifulSoup

def track_innovations():
    # URLs des sites web traitant des innovations en OSINT
    urls = ['https://www.osinttechniques.com/', 'https://www.intelligenceonline.com/']
    for url in urls:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Extraction des titres d'articles pertinents
        articles = soup.find_all('article')
        for article in articles:
            title = article.find('h2').text
            print(title)
track_innovations()