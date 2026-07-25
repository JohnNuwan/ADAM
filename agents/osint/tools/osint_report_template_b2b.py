def create_osint_report_template_b2b():
    # Créer un template de rapport OSINT B2B
    template = {
        'title': 'OSINT Report for B2B',
        'sections': [
            {'name': 'Executive Summary', 'content': ''},
            {'name': 'Company Overview', 'content': ''},
            {'name': 'Key Contacts', 'content': ''},
            {'name': 'Social Media Presence', 'content': ''},
            {'name': 'Digital Footprint Analysis', 'content': ''},
            {'name': 'Competitor Analysis', 'content': ''},
            {'name': 'Conclusion and Recommendations', 'content': ''}
        ],
        'footer': 'Confidential - For internal use only'
    }
    return template
