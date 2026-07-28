
import time
import threading
from datetime import datetime

class ContinuousSecurityWatchdog:
    def __init__(self, check_interval=60):
        self.check_interval = check_interval  # Time in seconds between checks
        self.is_running = False
        self.security_issues = []

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._monitor()

    def stop(self):
        self.is_running = False

    def _monitor(self):
        while self.is_running:
            self._check_security()
            time.sleep(self.check_interval)

    def _check_security(self):
        # Example of a security check: checking for unusual login times.
        current_time = datetime.now().hour
        if 1 <= current_time <= 6:
            self.security_issues.append(f"Unusual login detected at {datetime.now()}")
            print("ALERT: Unusual activity detected!")
        else:
            print(f"Security check at {datetime.now()}: No unusual activity.")

    def get_latest_security_issues(self):
        return self.security_issues[-5:]  # Return the last 5 issues

if __name__ == "__main__":
    watchdog = ContinuousSecurityWatchdog(check_interval=10)
    watchdog.start()

    # Running the watchdog for 1 minute then stopping it for demonstration purposes
    time.sleep(60)
    watchdog.stop()
    print("Latest security issues:", watchdog.get_latest_security_issues())
