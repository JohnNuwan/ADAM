def create_content_advice(trends):
    advice = []
    for trend in trends:
        # Generate content advice based on the trend
        advice.append(f"Create a post related to {trend}")
    return advice