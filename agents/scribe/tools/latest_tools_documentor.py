def latest_tools_documentor(system_data):
    # Extraire les informations sur les derniers outils créés
    latest_tools = [tool for tool in system_data['tools'] if tool['status'] == 'created_recently']
    # Générer la documentation pour chaque outil
    documentation = []
    for tool in latest_tools:
        doc_entry = {
            'name': tool['name'],
            'description': tool['description'],
            'creator': tool['creator'],
            'date_created': tool['date_created']
        }
        documentation.append(doc_entry)
    return documentation