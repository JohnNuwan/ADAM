def generate_report(cves):
    report = {}
    for cve in cves:
        # Simuler la récupération de détails sur chaque CVE
        details = {
            'description': 'Description de la vulnérabilité associée au CVE',
            'severity': 'Haute',
            'published_date': '2023-04-01'
        }
        report[cve] = details
    return report

# Utiliser les CVE obtenus précédemment pour générer un rapport
report = generate_report(last_cve)
print(report)