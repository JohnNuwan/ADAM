import instaloader
from collections import Counter

class TrendAnalyzer:
    def __init__(self):
        self.loader = instaloader.Instaloader()

    def analyze_trends(self, hashtag_list):
        top_posts = []
        for hashtag in hashtag_list:
            posts = instaloader.Hashtag.from_hashtag_name(hashtag, self.loader.context).get_top_posts()
            top_posts.extend(posts)

        # Collect and count the most common hashtags used in top posts
        all_hashtags = []
        for post in top_posts:
            all_hashtags.extend(post.caption.hashtags)

        common_hashtags = Counter(all_hashtags).most_common(10)
        return common_hashtags