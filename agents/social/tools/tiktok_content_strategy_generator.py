
import random

class TiktokContentStrategyGenerator:
    def __init__(self):
        self.content_types = ["dances", "challenges", "cooking", "vlogs", "tutorials"]
        self.target_audiences = ["teens", "young adults", "families", "professionals"]
        self.hashtags = ["#TikTokTrends", "#ViralVideo", "#DanceChallenge", "#CookingTime"]
        self.posting_schedule = ["daily", "twice_a_week", "thrice_a_week", "weekly"]

    def generate_strategy(self):
        content_type = random.choice(self.content_types)
        target_audience = random.choice(self.target_audiences)
        hashtag = random.choice(self.hashtags)
        posting = random.choice(self.posting_schedule)

        strategy = {
            "content_type": content_type,
            "target_audience": target_audience,
            "hashtag": hashtag,
            "posting_schedule": posting
        }
        return strategy

if __name__ == "__main__":
    generator = TiktokContentStrategyGenerator()
    strategy = generator.generate_strategy()
    print(strategy)
