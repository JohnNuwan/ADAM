
import pandas as pd

class PerformanceAnalysisSummary:
    def __init__(self):
        self.audit_results = []

    def add_audit_result(self, container_id, cpu_usage, memory_usage, disk_usage):
        self.audit_results.append({
            "container_id": container_id,
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage,
            "disk_usage": disk_usage
        })

    def generate_summary_report(self):
        df = pd.DataFrame(self.audit_results)
        summary_df = df.groupby('container_id').agg({
            'cpu_usage': ['mean', 'max', 'min'],
            'memory_usage': ['mean', 'max', 'min'],
            'disk_usage': ['mean', 'max', 'min']
        })
        return summary_df

    def find_problematic_containers(self, threshold_cpu=80, threshold_memory=80, threshold_disk=90):
        df = pd.DataFrame(self.audit_results)
        problematic_containers = df[(df['cpu_usage'] > threshold_cpu) |
                                     (df['memory_usage'] > threshold_memory) |
                                     (df['disk_usage'] > threshold_disk)]
        return problematic_containers

# Example usage:
if __name__ == "__main__":
    performance_tool = PerformanceAnalysisSummary()
    performance_tool.add_audit_result("container1", 75, 60, 30)
    performance_tool.add_audit_result("container2", 90, 85, 80)
    performance_tool.add_audit_result("container1", 78, 65, 35)
    performance_tool.add_audit_result("container3", 85, 80, 40)

    summary_report = performance_tool.generate_summary_report()
    print("Summary Report:")
    print(summary_report)

    problematic_containers = performance_tool.find_problematic_containers()
    print("\nProblematic Containers:")
    print(problematic_containers)
