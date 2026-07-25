import docker
from resource_monitor import ResourceMonitor

def identify_unnecessary_containers():
    client = docker.from_env()
    containers = client.containers.list()
    resource_monitor = ResourceMonitor()
    unnecessary_containers = []
    for container in containers:
        usage = resource_monitor.monitor(container)
        if usage['cpu'] < 5 and usage['memory'] < 5 and usage['gpu'] < 5:
            unnecessary_containers.append(container)
    return unnecessary_containers