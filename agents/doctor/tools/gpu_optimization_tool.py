from praetor.optimization_proposer import OptimizationProposer
from praetor.container_optimizer import ContainerOptimizer

# Crée une instance d'OptimizationProposer pour proposer des optimisations
gpu_optimizer = OptimizationProposer()

# Propose des optimisations pour les paramètres de batch et de quantification des RTX 3090
gpu_optimizations = gpu_optimizer.propose_optimizations('RTX 3090', ['batch_size', 'quantization'])

# Crée une instance de ContainerOptimizer pour appliquer les optimisations
container_optimizer = ContainerOptimizer()

# Applique les optimisations proposées aux conteneurs utilisant les RTX 3090
container_optimizer.apply_optimizations(gpu_optimizations)