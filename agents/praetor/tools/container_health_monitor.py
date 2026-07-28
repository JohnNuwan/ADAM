
import docker

def get_container_health(client):
    containers = client.containers.list()
    unhealthy_containers = []
    for container in containers:
        if container.status == 'running':
            health = container.attrs['State']['Health']
            if health and health['Status'] != 'healthy':
                unhealthy_containers.append((container.name, health['Status']))
    return unhealthy_containers

def monitor_health():
    client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    unhealthy_containers = get_container_health(client)
    if unhealthy_containers:
        print("Unhealthy containers found:")
        for name, status in unhealthy_containers:
            print(f"Container: {name}, Status: {status}")
    else:
        print("All containers are healthy.")

if __name__ == '__main__':
    monitor_health()
