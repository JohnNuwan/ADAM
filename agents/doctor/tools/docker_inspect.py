def docker_inspect(container_id):
    import subprocess
    result = subprocess.run(['docker', 'inspect', container_id], stdout=subprocess.PIPE)
    return result.stdout.decode('utf-8')