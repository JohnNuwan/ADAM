import pandas as pd
from datetime import datetime

def analyze_digital_trails(data):
    # Prétraitement des données
    data['timestamp'] = pd.to_datetime(data['timestamp'])
    data.sort_values('timestamp', inplace=True)

    # Identification des patterns et anomalies
    pattern_analysis = {}
    anomaly_detection = []

    for index, row in data.iterrows():
        timestamp = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        event = row['event']

        if event not in pattern_analysis:
            pattern_analysis[event] = {'first_occurrence': timestamp, 'count': 0}
        pattern_analysis[event]['count'] += 1

        if pattern_analysis[event]['count'] > 1 and pattern_analysis[event]['count'] % 10 == 0:
            anomaly_detection.append(f"Anomaly detected: {event} occurred {pattern_analysis[event]['count']} times since {pattern_analysis[event]['first_occurrence']}")

    return pattern_analysis, anomaly_detection