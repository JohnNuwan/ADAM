
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error

def load_data(file_path):
    return pd.read_csv(file_path)

def preprocess_data(data):
    data.dropna(inplace=True)
    return data

def train_model(data, target_column):
    X = data.drop(columns=[target_column])
    y = data[target_column]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = LinearRegression()
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)
    mse = mean_squared_error(y_test, predictions)
    print(f"Mean Squared Error: {mse}")
    return model

def main():
    file_path = 'path_to_your_data.csv'
    target_column = 'your_target_column_name'
    data = load_data(file_path)
    processed_data = preprocess_data(data)
    model = train_model(processed_data, target_column)

if __name__ == '__main__':
    main()
