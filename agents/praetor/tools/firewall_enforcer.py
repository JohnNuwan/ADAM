def enforce_firewalls(critical_services):
    for service in critical_services:
        # Mettre à jour les règles du pare-feu pour chaque service critique
        update_firewall_rules(service)
        # Vérifier que les règles sont correctement appliquées
        verify_firewall(service)