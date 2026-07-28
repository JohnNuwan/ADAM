
import random

class ProductIdeaGenerator:
    def __init__(self):
        self.market_analysis = {
            "technology": ["AI", "IoT", "Blockchain"],
            "healthcare": ["Telemedicine", "Wearable Devices", "Health Apps"],
            "education": ["Online Learning Platforms", "Virtual Reality Training", "Interactive Content"]
        }

    def generate_product_ideas(self, category=None):
        if category and category in self.market_analysis:
            ideas = self.market_analysis[category]
        else:
            ideas = [item for sublist in self.market_analysis.values() for item in sublist]

        return random.sample(ideas, min(len(ideas), 5))

# Example usage
if __name__ == "__main__":
    generator = ProductIdeaGenerator()
    print("General product ideas:", generator.generate_product_ideas())
    print("Technology product ideas:", generator.generate_product_ideas(category="technology"))
