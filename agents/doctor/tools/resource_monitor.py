def monitor_resources(container_id):
    import subprocess
    result = subprocess.run(['docker', 'stats', '--no-stream', container_id], stdout=subprocess.PIPE)
    output = result.stdout.decode('utf-8')
    return output