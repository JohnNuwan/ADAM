def generate_weekly_trend_report(trends_data):
    report = []
    for trend in trends_data:
        entry = {
            'hashtag': trend['hashtag'],
            'popularity_score': trend['popularity_score'],
            'top_posts': trend['top_posts']
        }
        report.append(entry)
    return report