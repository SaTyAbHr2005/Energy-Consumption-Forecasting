import os
import numpy as pd
import pandas as pd
from datetime import timedelta
import numpy as np
import json
from pathlib import Path

# Scikit-learn & XGBoost
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import MinMaxScaler
from xgboost import XGBRegressor

# Statsmodels
from statsmodels.tsa.statespace.sarimax import SARIMAX

# TensorFlow/Keras
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

import warnings
warnings.filterwarnings("ignore")

class DataSplitter:
    @staticmethod
    def chronological_split(df: pd.DataFrame, train_ratio=0.7, val_ratio=0.15):
        df = df.sort_values("timestamp").reset_index(drop=True)
        n = len(df)
        train_end = int(n * train_ratio)
        val_end = train_end + int(n * val_ratio)
        
        train_df = df.iloc[:train_end].copy()
        val_df = df.iloc[train_end:val_end].copy()
        test_df = df.iloc[val_end:].copy()
        
        return train_df, val_df, test_df

class FeatureRebuilder:
    @staticmethod
    def build_next_feature_vector(history_df: pd.DataFrame, next_timestamp: pd.Timestamp, p90_threshold: float, feature_cols: list) -> pd.DataFrame:
        """Builds the feature vector for a future timestamp using pure history."""
        # Calendar & cyclical
        h = next_timestamp.hour
        d = next_timestamp.day
        m = next_timestamp.month
        dow = next_timestamp.weekday()
        
        row = {}
        row['year'] = next_timestamp.year
        row['month'] = m
        row['day'] = d
        row['day_of_month'] = d
        row['day_of_week'] = dow
        row['hour'] = h
        row['week_of_year'] = next_timestamp.isocalendar()[1]
        row['quarter'] = next_timestamp.quarter
        row['is_weekend'] = 1 if dow in [5, 6] else 0
        
        row['hour_sin'] = np.sin(2 * np.pi * h / 24)
        row['hour_cos'] = np.cos(2 * np.pi * h / 24)
        row['dow_sin'] = np.sin(2 * np.pi * dow / 7)
        row['dow_cos'] = np.cos(2 * np.pi * dow / 7)
        row['month_sin'] = np.sin(2 * np.pi * m / 12)
        row['month_cos'] = np.cos(2 * np.pi * m / 12)
        
        # Historical target array
        energy_history = history_df['energy_kwh'].values
        
        # Lags
        for lag in [1, 3, 6, 12, 24, 48, 72, 168]:
            row[f'lag_{lag}'] = energy_history[-lag] if len(energy_history) >= lag else np.nan
            
        # Rolling
        for w in [3, 6, 12, 24, 168]:
            if len(energy_history) >= w:
                window = energy_history[-w:]
                row[f'rolling_mean_{w}'] = np.mean(window)
                if w == 24:
                    # pd.Series for sample stddev like spark
                    row[f'rolling_std_{w}'] = pd.Series(window).std()
                    row[f'rolling_min_{w}'] = np.min(window)
                    row[f'rolling_max_{w}'] = np.max(window)
            else:
                row[f'rolling_mean_{w}'] = np.nan
                if w == 24:
                    row[f'rolling_std_{w}'] = np.nan
                    row[f'rolling_min_{w}'] = np.nan
                    row[f'rolling_max_{w}'] = np.nan
                    
        # Trend
        if len(energy_history) >= 3:
            row['trend_3h'] = energy_history[-1] - energy_history[-3]
        else:
            row['trend_3h'] = np.nan
            
        if len(energy_history) >= 24:
            row['trend_24h'] = energy_history[-1] - energy_history[-24]
        else:
            row['trend_24h'] = np.nan
            
        # Contextual
        if len(energy_history) >= 1:
            row['is_high_demand_previous_hour'] = 1 if energy_history[-1] >= p90_threshold else 0
        else:
            row['is_high_demand_previous_hour'] = 0

        # Filter to only requested feature_cols exactly
        out = {k: row[k] for k in feature_cols if k in row}
        return pd.DataFrame([out])

class NaiveForecaster:
    def predict_1h(self, df):
        # Baseline A: previous hour (lag_1)
        res = df[['timestamp', 'energy_kwh']].copy()
        res['predicted'] = df['lag_1']
        res['horizon'] = 1
        res['model'] = 'Naive_1h'
        res = res.rename(columns={'energy_kwh': 'actual'})
        return res

    def predict_24h(self, df):
        # Baseline B: same hour previous day (lag_24)
        res = df[['timestamp', 'energy_kwh']].copy()
        res['predicted'] = df['lag_24']
        res['horizon'] = 24
        res['model'] = 'Naive_24h'
        res = res.rename(columns={'energy_kwh': 'actual'})
        return res

class SARIMAModelWrapper:
    def __init__(self, order=(1, 0, 0), seasonal_order=(1, 0, 0, 24)):
        self.order = order
        self.seasonal_order = seasonal_order
        self.model = None
        self.results = None

    def fit(self, train_series):
        # Train SARIMA
        self.model = SARIMAX(train_series, order=self.order, seasonal_order=self.seasonal_order, 
                             enforce_stationarity=False, enforce_invertibility=False)
        self.results = self.model.fit(disp=False)

    def predict_1h(self, df, history_series):
        # One-step ahead for test set using apply (fast filter)
        # To avoid refitting, we append the test set to the known history, without retraining
        res = df[['timestamp', 'energy_kwh']].copy()
        updated_res = self.results.apply(df['energy_kwh'])
        # Predict 1 step ahead (in-sample for the test set)
        preds = updated_res.predict(start=0, end=len(df)-1)
        res['predicted'] = preds.values
        res['horizon'] = 1
        res['model'] = 'SARIMA'
        res = res.rename(columns={'energy_kwh': 'actual'})
        return res
        
    def forecast_24h(self, steps=24):
        # Pure 24h future forecast from end of known data
        forecast = self.results.forecast(steps=steps)
        return forecast.values

class TreeForecaster:
    def __init__(self, model_type='rf', **kwargs):
        self.model_type = model_type
        if model_type == 'rf':
            self.model = RandomForestRegressor(**kwargs)
        elif model_type == 'xgb':
            self.model = XGBRegressor(**kwargs)
        self.feature_cols = []
        self.p90_threshold = None

    def fit(self, X_train, y_train, p90_threshold, feature_cols):
        self.feature_cols = feature_cols
        self.p90_threshold = p90_threshold
        self.model.fit(X_train[self.feature_cols], y_train)

    def predict_1h(self, df):
        preds = self.model.predict(df[self.feature_cols])
        res = df[['timestamp', 'energy_kwh']].copy()
        res['predicted'] = preds
        res['horizon'] = 1
        res['model'] = 'RandomForest' if self.model_type == 'rf' else 'XGBoost'
        res = res.rename(columns={'energy_kwh': 'actual'})
        return res

    def predict_24h_recursive(self, history_df, start_timestamp, steps=24):
        current_history = history_df.copy()
        predictions = []
        timestamps = []
        
        current_ts = start_timestamp
        
        for h in range(1, steps + 1):
            next_feat = FeatureRebuilder.build_next_feature_vector(
                current_history, current_ts, self.p90_threshold, self.feature_cols
            )
            
            # Ensure correct column order
            pred = self.model.predict(next_feat[self.feature_cols])[0]
            
            # Append prediction to history so next step can use it
            new_row = pd.DataFrame([{'timestamp': current_ts, 'energy_kwh': pred}])
            current_history = pd.concat([current_history, new_row], ignore_index=True)
            
            predictions.append(pred)
            timestamps.append(current_ts)
            
            current_ts += timedelta(hours=1)
            
        res = pd.DataFrame({
            'timestamp': timestamps,
            'actual': [np.nan] * steps,
            'predicted': predictions,
            'horizon': range(1, steps + 1),
            'model': 'RandomForest' if self.model_type == 'rf' else 'XGBoost'
        })
        return res

class LSTMForecaster:
    def __init__(self, seq_length=168, epochs=10, batch_size=64):
        self.seq_length = seq_length
        self.epochs = epochs
        self.batch_size = batch_size
        self.model = None
        self.scaler = MinMaxScaler()
        self.history = None

    def _create_sequences(self, data):
        X, y = [], []
        for i in range(len(data) - self.seq_length):
            X.append(data[i:i + self.seq_length])
            y.append(data[i + self.seq_length])
        return np.array(X), np.array(y)

    def fit(self, train_series, val_series):
        # Scale
        train_scaled = self.scaler.fit_transform(train_series.values.reshape(-1, 1))
        val_scaled = self.scaler.transform(val_series.values.reshape(-1, 1))
        
        X_train, y_train = self._create_sequences(train_scaled)
        X_val, y_val = self._create_sequences(val_scaled)
        
        # Model
        tf.random.set_seed(42)
        self.model = Sequential([
            LSTM(64, activation='relu', input_shape=(self.seq_length, 1)),
            Dropout(0.2),
            Dense(1)
        ])
        self.model.compile(optimizer='adam', loss='mse')
        
        self.history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=self.epochs,
            batch_size=self.batch_size,
            verbose=1
        )

    def predict_1h(self, test_series, df_test_timestamps):
        # We need historical context for test_series. 
        # test_series should include the preceding `seq_length` items from val!
        scaled_data = self.scaler.transform(test_series.values.reshape(-1, 1))
        X_test, _ = self._create_sequences(scaled_data)
        
        preds_scaled = self.model.predict(X_test, verbose=0)
        preds = self.scaler.inverse_transform(preds_scaled).flatten()
        
        # Align timestamps (first seq_length items were history)
        actuals = test_series.values[self.seq_length:]
        timestamps = df_test_timestamps.values[self.seq_length:]
        
        res = pd.DataFrame({
            'timestamp': timestamps,
            'actual': actuals,
            'predicted': preds,
            'horizon': 1,
            'model': 'LSTM'
        })
        return res

    def predict_24h_recursive(self, history_series, start_timestamp, steps=24):
        # history_series must be exactly seq_length
        current_seq = self.scaler.transform(history_series.values.reshape(-1, 1)).flatten().tolist()
        
        predictions = []
        timestamps = []
        current_ts = start_timestamp
        
        for _ in range(steps):
            X_in = np.array(current_seq[-self.seq_length:]).reshape(1, self.seq_length, 1)
            pred_scaled = self.model.predict(X_in, verbose=0)[0, 0]
            
            pred = self.scaler.inverse_transform([[pred_scaled]])[0, 0]
            predictions.append(pred)
            timestamps.append(current_ts)
            
            # append scaled prediction to history
            current_seq.append(pred_scaled)
            current_ts += timedelta(hours=1)
            
        res = pd.DataFrame({
            'timestamp': timestamps,
            'actual': [np.nan] * steps,
            'predicted': predictions,
            'horizon': range(1, steps + 1),
            'model': 'LSTM'
        })
        return res
