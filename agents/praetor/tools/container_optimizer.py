def optimize_containers(containers_data):
    optimized_containers = []
    for container in containers_data:
        # Appliquer les meilleures pratiques en matière d'optimisation des conteneurs
        if container['performance'] < container['expected_performance']:
            # Proposer des améliorations spécifiques pour chaque conteneur
            optimized_containers.append({'id': container['id'], 'improvements': ['reduce_memory_usage', 'increase_cpu_allocation']})
    return optimized_containers