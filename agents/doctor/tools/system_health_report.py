from docker_inspect import DockerInspect
from resource_monitor import ResourceMonitor

def generate_system_health_report():
    docker_inspector = DockerInspect()
    resource_monitor = ResourceMonitor()
    report = {}
    containers = docker_inspector.inspect()
    for container in containers:
        usage = resource_monitor.monitor(container)
        report[container.name] = {
            'status': container.status,
            'resources_usage': usage
        }
    return report