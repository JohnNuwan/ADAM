
import json

def parse_docker_inspect(data):
    """
    Parse the output of docker inspect to extract relevant information.
    """
    parsed_data = []
    for container in data:
        container_info = {
            "id": container["Id"],
            "image": container["Config"]["Image"],
            "state": container["State"]["Status"]
        }
        parsed_data.append(container_info)
    return parsed_data

def parse_resource_monitor(data):
    """
    Parse the output of resource monitor to extract CPU and memory usage.
    """
    parsed_data = {}
    for entry in data:
        container_id = entry["container_id"]
        cpu_usage = entry["cpu_usage"]
        mem_usage = entry["mem_usage"]
        parsed_data[container_id] = {"cpu": cpu_usage, "mem": mem_usage}
    return parsed_data

def identify_unused_containers(docker_data, resource_data, cpu_threshold=0.1, mem_threshold=1024):
    """
    Identify containers that are unused based on CPU and memory thresholds.
    """
    unused_containers = []
    for container in docker_data:
        container_id = container["id"]
        if container_id in resource_data:
            cpu_usage = resource_data[container_id]["cpu"]
            mem_usage = resource_data[container_id]["mem"]
            if cpu_usage < cpu_threshold and mem_usage < mem_threshold:
                unused_containers.append(container_id)
    return unused_containers

if __name__ == '__main__':
    docker_inspect_output = [
        {"Id": "abc123", "Config": {"Image": "nginx"}, "State": {"Status": "running"}},
        {"Id": "def456", "Config": {"Image": "mysql"}, "State": {"Status": "paused"}}
    ]
    resource_monitor_output = [
        {"container_id": "abc123", "cpu_usage": 0.05, "mem_usage": 512},
        {"container_id": "def456", "cpu_usage": 0.9, "mem_usage": 8192}
    ]
    parsed_docker_data = parse_docker_inspect(docker_inspect_output)
    parsed_resource_data = parse_resource_monitor(resource_monitor_output)
    unused_containers = identify_unused_containers(parsed_docker_data, parsed_resource_data)
    print("Unused containers:", unused_containers)
