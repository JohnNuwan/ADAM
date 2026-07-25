def seo_article_writer(topics):
    import random
    from datetime import datetime

    # Simulate a function that generates SEO optimized articles based on topics provided.
    def generate_seo_content(topic):
        # Here we would use an AI to generate the actual content, but for now,
        # we'll simulate this with a placeholder string.
        return f'SEO Optimized Article on {topic} - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'

    # List of generated articles
    articles = []

    # Generate 3 articles
    for topic in random.sample(topics, min(3, len(topics))):
        article = generate_seo_content(topic)
        articles.append(article)

    return articles

# Example usage
articles = seo_article_writer(['AI Development', 'System Optimization', 'Data Analysis'])
print(articles)