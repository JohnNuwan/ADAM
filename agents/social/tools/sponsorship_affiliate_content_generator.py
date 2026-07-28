
class SponsorshipAffiliateContentGenerator:
    def __init__(self, brand_identity, audience_interests):
        self.brand_identity = brand_identity
        self.audience_interests = audience_interests

    def generate_content_ideas(self, monetization_opportunities):
        content_ideas = []
        for opportunity in monetization_opportunities:
            aligned_brands = [brand for brand in self.brand_identity if opportunity['brand'] in brand]
            aligned_audience = [interest for interest in self.audience_interests if opportunity['interest'] in interest]

            if aligned_brands and aligned_audience:
                idea = f"Create a post about {opportunity['topic']} featuring {opportunity['product']} to engage with the audience interested in {', '.join(aligned_audience)}"
                content_ideas.append(idea)
        return content_ideas

# Example usage
if __name__ == "__main__":
    brand_identity = ["tech innovation", "clean technology", "AI advancement"]
    audience_interests = ["coding", "AI", "machine learning", "sustainability"]

    generator = SponsorshipAffiliateContentGenerator(brand_identity, audience_interests)

    monetization_opportunities = [
        {"brand": "tech innovation", "product": "new AI software", "interest": "AI", "topic": "artificial intelligence"},
        {"brand": "clean technology", "product": "eco-friendly gadgets", "interest": "sustainability", "topic": "green tech"},
        {"brand": "non-aligned brand", "product": "outdated tech", "interest": "legacy systems", "topic": "old tech"}
    ]

    ideas = generator.generate_content_ideas(monetization_opportunities)
    for idea in ideas:
        print(idea)
