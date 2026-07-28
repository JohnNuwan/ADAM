
import random

class Container:
    def __init__(self, name, performance):
        self.name = name
        self.performance = performance  # Performance is measured as a percentage of optimal.

    def optimize(self):
        # Simple optimization algorithm that increases performance by a random amount.
        improvement = random.uniform(0.05, 0.2)  # 5% to 20%
        self.performance += improvement
        if self.performance > 1.0:
            self.performance = 1.0  # Cap at 100% performance
        return f"Container {self.name} optimized, new performance: {self.performance * 100:.2f}%"

class ContainerOptimizer:
    def __init__(self, containers):
        self.containers = containers  # List of Container objects

    def identify_underperforming_containers(self):
        underperforming = [c for c in self.containers if c.performance < 0.9]
        return underperforming

    def suggest_improvements(self):
        underperforming_containers = self.identify_underperforming_containers()
        improvements = []
        for container in underperforming_containers:
            improvements.append(container.optimize())
        return improvements

# Example usage
if __name__ == "__main__":
    containers = [
        Container("web-app-1", 0.8),
        Container("db-service-1", 0.75),
        Container("cache-1", 0.95)
    ]
    optimizer = ContainerOptimizer(containers)
    suggestions = optimizer.suggest_improvements()
    for suggestion in suggestions:
        print(suggestion)
