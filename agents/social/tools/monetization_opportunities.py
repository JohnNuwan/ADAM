def monetization_opportunities(trends):
    # Analyse des opportunités de monétisation basées sur les tendances
    opportunities = []
    for trend in trends:
        if 'sponsoring' in trend or 'affiliation' in trend:
            opportunities.append({'theme': trend, 'type': 'sponsoring/affiliation'})
    return opportunities