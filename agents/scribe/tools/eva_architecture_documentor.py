def create_eva_architecture_documentor(system_data):
    # Utiliser les données recueillies par system_status_checker pour créer un document détaillé sur l'architecture d'EVA
    architecture_doc = ""
    for component in system_data:
        architecture_doc += f"Component: {component['name']}, Description: {component['description']}, Interactions: {component['interactions']}\n"
    return architecture_doc