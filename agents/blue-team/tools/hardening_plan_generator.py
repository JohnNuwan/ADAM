def generate_hardening_plan(vulnerabilities):
    plan = []
    for vulnerability in vulnerabilities:
        # Générer des actions correctives
        corrective_action = f'Remédier à {vulnerability}'
        plan.append({'vulnerability': vulnerability, 'corrective_action': corrective_action})
    return plan