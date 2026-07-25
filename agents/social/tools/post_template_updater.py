def update_templates(current_templates, new_templates):
    updated_templates = {**current_templates, **new_templates}
    return updated_templates

with open('existing_templates.json', 'r') as file:
    current_templates = json.load(file)

with open(new_templates, 'r') as file:
    new_templates_data = json.load(file)

updated_templates = update_templates(current_templates, new_templates_data)

with open('existing_templates.json', 'w') as file:
    json.dump(updated_templates, file)