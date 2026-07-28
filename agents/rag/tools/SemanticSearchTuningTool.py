from praetor.agent_performance_analyzer import AgentPerformanceAnalyzer
from praetor.optimization_proposer import OptimizationProposer

class SemanticSearchTuningTool:
    def __init__(self):
        self.performance_analyzer = AgentPerformanceAnalyzer()
        self.optimizer = OptimizationProposer()

    def propose_optimizations(self, parameters):
        performance_data = self.performance_analyzer.analyze_performance(parameters)
        optimizations = self.optimizer.propose_optimizations(performance_data)
        return optimizations

    def apply_optimizations(self, optimizations):
        # Appliquer les optimisations proposées
        pass