def eva_architecture_documentor(system_data):
    # Utiliser les données collectées pour documenter l'architecture d'EVA
    architecture_doc = ''
    for component in system_data['components']:
        architecture_doc += f'- {component}: {system_data[component]}\n'
    return architecture_doc