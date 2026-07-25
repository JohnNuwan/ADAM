class ContainerCleaner:
    def __init__(self, unused_containers):
        self.unused_containers = unused_containers

    def clean_containers(self):
        for container in self.unused_containers:
            # Logique de suppression des conteneurs inutiles
            pass