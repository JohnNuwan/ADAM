
import numpy as np
from scipy.optimize import minimize

def objective_function(x):
    return np.sum(x**2)

def constraint_function(x):
    return np.sum(x) - 1

def performance_optimization():
    x0 = np.array([2, 2])
    constraints = {'type': 'eq', 'fun': constraint_function}
    result = minimize(objective_function, x0, method='SLSQP', constraints=constraints)
    return result.x

if __name__ == '__main__':
    optimized_solution = performance_optimization()
    print(optimized_solution)
