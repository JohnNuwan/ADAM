def optimize_performance(analysis_results):
    optimizations = []
    for result in analysis_results:
        if 'bottleneck' in result:
            optimizations.append({'target': result['target'], 'improvement': 'increase_capacity'})
        elif 'inefficiency' in result:
            optimizations.append({'target': result['target'], 'improvement': 'refactor_code'})
    return optimizations
