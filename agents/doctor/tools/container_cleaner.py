
import subprocess

def get_containers_to_remove():
    # Simulate the retrieval of containers to remove
    return ['container1', 'container2']

def remove_container(container_id):
    try:
        subprocess.run(['docker', 'rm', '-f', container_id], check=True)
        print(f"Container {container_id} removed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to remove container {container_id}: {e}")

def container_cleaner():
    containers = get_containers_to_remove()
    for container in containers:
        remove_container(container)

if __name__ == '__main__':
    container_cleaner()
