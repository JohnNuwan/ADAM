
import requests
from bs4 import BeautifulSoup
import pandas as pd

def fetch_api_data(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    api_list = []
    for item in soup.find_all('div', class_='api-item'):
        name = item.find('h2').text
        description = item.find('p').text
        price = item.find('span', class_='price').text
        api_list.append({'name': name, 'description': description, 'price': price})
    return api_list

def analyze_market(api_list):
    df = pd.DataFrame(api_list)
    df['price'] = df['price'].str.replace('$', '').astype(float)
    top_apis = df.nlargest(3, 'price')
    return top_apis.to_dict('records')

def main():
    url = 'https://example.com/api-market'
    api_list = fetch_api_data(url)
    top_apis = analyze_market(api_list)
    print(top_apis)

if __name__ == '__main__':
    main()
