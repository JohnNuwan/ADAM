import psutil
def check_system_status():
    # CPU usage
    cpu_usage = psutil.cpu_percent(1)
    # Memory usage
    memory = psutil.virtual_memory()
    memory_usage = memory.percent
    # Disk usage
    disk = psutil.disk_usage('/')
    disk_usage = disk.percent
    return {'cpu_usage': cpu_usage, 'memory_usage': memory_usage, 'disk_usage': disk_usage}