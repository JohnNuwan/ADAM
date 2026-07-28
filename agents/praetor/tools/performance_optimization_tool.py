
import psutil
import docker
from datetime import datetime

client = docker.from_env()

def get_container_stats(container):
    stats = container.stats(stream=False)
    cpu_delta = float(stats["cpu_stats"]["cpu_usage"]["total_usage"]) - float(stats["precpu_stats"]["cpu_usage"]["total_usage"])
    system_delta = float(stats["cpu_stats"]["system_cpu_usage"]) - float(stats["precpu_stats"]["system_cpu_usage"])
    cpu_usage = (cpu_delta / system_delta) * len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"]) * 100.0
    mem_usage = (float(stats["memory_stats"]["usage"]) / float(stats["memory_stats"]["limit"])) * 100.0
    return {"cpu_usage": cpu_usage, "mem_usage": mem_usage}

def analyze_performance():
    containers = client.containers.list()
    for container in containers:
        stats = get_container_stats(container)
        if stats['cpu_usage'] > 90 or stats['mem_usage'] > 90:
            print(f"Container {container.name} has high usage: CPU {stats['cpu_usage']}%, Memory {stats['mem_usage']}%")

def optimize_performance():
    containers = client.containers.list()
    for container in containers:
        stats = get_container_stats(container)
        if stats['cpu_usage'] > 90:
            print(f"Optimizing CPU for container {container.name}")
            # Add logic to optimize CPU here
        if stats['mem_usage'] > 90:
            print(f"Optimizing Memory for container {container.name}")
            # Add logic to optimize memory here

if __name__ == '__main__':
    analyze_performance()
    optimize_performance()
