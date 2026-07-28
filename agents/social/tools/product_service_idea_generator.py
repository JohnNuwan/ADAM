
import random
import requests

class ProductServiceIdeaGenerator:
    def __init__(self):
        self.market_data = self.fetch_market_data()
        self.trends = self.fetch_trends()
    
    def fetch_market_data(self):
        # Simulating fetching market data from an API
        return {
            "consumer_goods": {"demand": 75, "competition": 60},
            "tech_services": {"demand": 85, "competition": 90},
            "health_and_wellness": {"demand": 90, "competition": 70}
        }
    
    def fetch_trends(self):
        # Simulating fetching trends from an API
        return ["AI", "Sustainability", "Remote Work"]
    
    def generate_ideas(self):
        ideas = []
        for category in self.market_data.keys():
            if self.market_data[category]["demand"] > self.market_data[category]["competition"]:
                trend = random.choice(self.trends)
                idea = f"{trend} {category}"
                ideas.append(idea)
        return ideas

if __name__ == "__main__":
    generator = ProductServiceIdeaGenerator()
    ideas = generator.generate_ideas()
    print("Generated Product/Service Ideas:")
    for i, idea in enumerate(ideas, 1):
        print(f"{i}. {idea}")
