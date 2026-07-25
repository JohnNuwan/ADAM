def fix_errors(system_status):
    if system_status['cpu_usage'] > 90:
        return 'CPU usage is too high. Taking action to reduce load...'
    elif system_status['memory_usage'] > 90:
        return 'Memory usage is too high. Freeing up memory...'
    elif system_status['disk_usage'] > 90:
        return 'Disk usage is too high. Deleting unnecessary files...'
    else:
        return 'System status is normal.'