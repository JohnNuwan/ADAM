
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt

class MarketInsightsTool:
    def __init__(self, data_path):
        self.data = pd.read_csv(data_path)
        self.processed_data = None

    def preprocess_data(self):
        # Drop any rows with missing values for simplicity
        self.data.dropna(inplace=True)
        # Standardize the features
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(self.data)
        self.processed_data = pd.DataFrame(scaled_features, columns=self.data.columns)

    def perform_pca(self, n_components=2):
        if self.processed_data is None:
            raise ValueError("Data must be preprocessed before performing PCA.")
        pca = PCA(n_components=n_components)
        principal_components = pca.fit_transform(self.processed_data)
        return pd.DataFrame(principal_components, columns=[f"PC{i+1}" for i in range(n_components)])

    def visualize_pca(self, pca_df):
        plt.figure(figsize=(8, 6))
        plt.scatter(pca_df['PC1'], pca_df['PC2'])
        plt.xlabel('Principal Component 1')
        plt.ylabel('Principal Component 2')
        plt.title('PCA of Market Data')
        plt.show()

    def analyze_customer_interests(self):
        if self.processed_data is None:
            raise ValueError("Data must be preprocessed before analysis.")
        # Example analysis: Correlation between different features
        correlation_matrix = self.processed_data.corr()
        plt.figure(figsize=(10, 8))
        plt.imshow(correlation_matrix, cmap='coolwarm', aspect='auto')
        plt.colorbar()
        plt.title('Correlation Matrix of Processed Data')
        plt.show()

# Example usage
if __name__ == "__main__":
    tool = MarketInsightsTool('path_to_market_data.csv')
    tool.preprocess_data()
    pca_result = tool.perform_pca()
    tool.visualize_pca(pca_result)
    tool.analyze_customer_interests()
