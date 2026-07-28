import psutil
import platform
import datetime
import socket
import os

def system_status_checker():
    """
    Check the status of various components of the system.
    Returns a dictionary with system status data.
    """
    system_status_data = {}
    
    # CPU information
    system_status_data['cpu_percent'] = psutil.cpu_percent(interval=1)
    system_status_data['cpu_count'] = psutil.cpu_count()
    system_status_data['cpu_freq'] = psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
    
    # Memory information
    memory = psutil.virtual_memory()
    system_status_data['memory_total'] = memory.total
    system_status_data['memory_available'] = memory.available
    system_status_data['memory_percent'] = memory.percent
    system_status_data['memory_used'] = memory.used
    
    # Disk information
    disk = psutil.disk_usage('/')
    system_status_data['disk_total'] = disk.total
    system_status_data['disk_used'] = disk.used
    system_status_data['disk_free'] = disk.free
    system_status_data['disk_percent'] = disk.percent
    
    # Network information
    net_io = psutil.net_io_counters()
    system_status_data['net_bytes_sent'] = net_io.bytes_sent
    system_status_data['net_bytes_recv'] = net_io.bytes_recv
    system_status_data['net_packets_sent'] = net_io.packets_sent
    system_status_data['net_packets_recv'] = net_io.packets_recv
    
    # System information
    system_status_data['system'] = platform.system()
    system_status_data['node'] = platform.node()
    system_status_data['release'] = platform.release()
    system_status_data['version'] = platform.version()
    system_status_data['machine'] = platform.machine()
    system_status_data['processor'] = platform.processor()
    
    # Boot time
    boot_time_timestamp = psutil.boot_time()
    boot_time = datetime.datetime.fromtimestamp(boot_time_timestamp)
    system_status_data['boot_time'] = boot_time.isoformat()
    
    # Current time
    system_status_data['current_time'] = datetime.datetime.now().isoformat()
    
    # Hostname and IP
    system_status_data['hostname'] = socket.gethostname()
    try:
        system_status_data['ip_address'] = socket.gethostbyname(socket.gethostname())
    except socket.gaierror:
        system_status_data['ip_address'] = '127.0.0.1'
    
    # Process count
    system_status_data['process_count'] = len(psutil.pids())
    
    # Load average (if available)
    if hasattr(os, 'getloadavg'):
        load_avg = os.getloadavg()
        system_status_data['load_avg_1min'] = load_avg[0]
        system_status_data['load_avg_5min'] = load_avg[1]
        system_status_data['load_avg_15min'] = load_avg[2]
    
    return system_status_data

if __name__ == '__main__':
    status = system_status_checker()
    for key, value in status.items():
        print(f"{key}: {value}")