
import threading
import time
from datetime import datetime

class RealTimeSecurityMonitoring:
    def __init__(self):
        self.alerts = []
        self.is_running = False

    def start_monitoring(self):
        if not self.is_running:
            self.is_running = True
            monitoring_thread = threading.Thread(target=self.monitor_system)
            monitoring_thread.start()

    def stop_monitoring(self):
        self.is_running = False

    def monitor_system(self):
        while self.is_running:
            # Simulate security checks here
            if self.detect_unusual_activity():
                self.trigger_alert("Unusual activity detected")
            time.sleep(5)  # Check every 5 seconds

    def detect_unusual_activity(self):
        # Placeholder for actual detection logic
        return datetime.now().second % 10 == 0  # Simulate unusual activity every 10 seconds

    def trigger_alert(self, message):
        alert = {"timestamp": datetime.now(), "message": message}
        self.alerts.append(alert)
        print(f"ALERT: {alert['timestamp']} - {alert['message']}")

# Example usage
if __name__ == "__main__":
    security_monitor = RealTimeSecurityMonitoring()
    try:
        security_monitor.start_monitoring()
        time.sleep(30)  # Run for 30 seconds
    finally:
        security_monitor.stop_monitoring()
