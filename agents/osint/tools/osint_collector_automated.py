import osint_collector
import email_scraper

def osint_collector_automated(sources, target):
    # Collecte des informations OSINT depuis les sources spécifiées
    collected_data = {}
    for source in sources:
        if source == 'LinkedIn':
            collected_data[source] = osint_collector.collect_from_linkedin(target)
        elif source == 'Twitter':
            collected_data[source] = osint_collector.collect_from_twitter(target)
    
    # Scrapping des emails associés à la cible si nécessaire
    if 'email' not in collected_data:
        collected_data['email'] = email_scraper.scrape_emails(target)
    
    return collected_data
