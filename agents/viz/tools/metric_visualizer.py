
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def generate_metric_data(num_points):
    x = np.random.rand(num_points)
    y = np.random.rand(num_points)
    z = np.sin(x * np.pi) * np.cos(y * np.pi)
    return x, y, z

def metric_visualizer(x, y, z):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.scatter(x, y, z, c=z, cmap='viridis', linewidth=0.5)
    ax.set_xlabel('X axis')
    ax.set_ylabel('Y axis')
    ax.set_zlabel('Z axis')
    plt.show()

if __name__ == '__main__':
    num_points = 100
    x, y, z = generate_metric_data(num_points)
    metric_visualizer(x, y, z)
