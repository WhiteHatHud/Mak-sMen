"""
Data Preprocessing for Autoencoder-based Anomaly Detection
Converts system call traces into sequences for deep learning
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder, StandardScaler
import pickle


class SequencePreprocessor:
    """
    Preprocesses system call data into sequences for autoencoder training.
    """

    def __init__(self, sequence_length=50, stride=25):
        """
        Args:
            sequence_length: Number of events per sequence
            stride: Step size for sliding window
        """
        self.sequence_length = sequence_length
        self.stride = stride
        self.event_encoder = LabelEncoder()
        self.process_encoder = LabelEncoder()
        self.scaler = StandardScaler()

        self.feature_cols = [
            'eventId_encoded',
            'processName_encoded',
            'userId',
            'threadId',
            'argsNum',
            'returnValue',
            'sus'
        ]

    def create_sequences(self, df, fit_encoders=True):
        """
        Create sliding window sequences from system call traces.

        Args:
            df: DataFrame with system call data
            fit_encoders: Whether to fit encoders (True for training, False for test)

        Returns:
            sequences: Array of sequences (n_sequences, seq_length, n_features)
            labels: Labels for each sequence
            metadata: Process and host info
        """
        print(f"Creating sequences from {len(df)} events...")

        # Sort by host, process, and timestamp
        df = df.sort_values(['hostName', 'processId', 'timestamp']).reset_index(drop=True)

        # Encode categorical features
        if fit_encoders:
            df['eventId_encoded'] = self.event_encoder.fit_transform(df['eventName'])
            df['processName_encoded'] = self.process_encoder.fit_transform(df['processName'])
        else:
            # Handle unknown categories
            df['eventId_encoded'] = df['eventName'].map(
                lambda x: self.event_encoder.transform([x])[0]
                if x in self.event_encoder.classes_ else -1
            )
            df['processName_encoded'] = df['processName'].map(
                lambda x: self.process_encoder.transform([x])[0]
                if x in self.process_encoder.classes_ else -1
            )

        sequences = []
        labels = []
        metadata = []

        # Group by process to create sequences
        grouped = df.groupby(['hostName', 'processId'])

        print(f"Processing {len(grouped)} unique processes...")

        for idx, (name, group) in enumerate(grouped):
            if idx % 1000 == 0:
                print(f"  Processed {idx}/{len(grouped)} processes...")

            host, pid = name

            # Extract features
            process_data = group[self.feature_cols].values
            process_labels = group['evil'].values

            # Create sliding windows
            for i in range(0, len(process_data) - self.sequence_length + 1, self.stride):
                seq = process_data[i:i + self.sequence_length]
                label = process_labels[i:i + self.sequence_length].max()  # Any evil = evil

                sequences.append(seq)
                labels.append(label)
                metadata.append({
                    'hostName': host,
                    'processId': pid,
                    'start_idx': i
                })

        print(f"Created {len(sequences)} sequences")

        return np.array(sequences), np.array(labels), metadata

    def scale_sequences(self, sequences, fit=True):
        """
        Normalize sequence features.

        Args:
            sequences: Array of sequences
            fit: Whether to fit scaler (True for training)

        Returns:
            Scaled sequences
        """
        print("Scaling sequences...")

        n_samples, seq_len, n_features = sequences.shape

        # Reshape for scaling
        sequences_flat = sequences.reshape(-1, n_features)

        # Scale
        if fit:
            sequences_scaled = self.scaler.fit_transform(sequences_flat)
        else:
            sequences_scaled = self.scaler.transform(sequences_flat)

        # Reshape back
        sequences_scaled = sequences_scaled.reshape(n_samples, seq_len, n_features)

        return sequences_scaled

    def save(self, filepath):
        """Save preprocessor state"""
        with open(filepath, 'wb') as f:
            pickle.dump({
                'event_encoder': self.event_encoder,
                'process_encoder': self.process_encoder,
                'scaler': self.scaler,
                'feature_cols': self.feature_cols,
                'sequence_length': self.sequence_length,
                'stride': self.stride
            }, f)
        print(f"Preprocessor saved to {filepath}")

    @classmethod
    def load(cls, filepath):
        """Load preprocessor state"""
        with open(filepath, 'rb') as f:
            state = pickle.load(f)

        preprocessor = cls(
            sequence_length=state['sequence_length'],
            stride=state['stride']
        )
        preprocessor.event_encoder = state['event_encoder']
        preprocessor.process_encoder = state['process_encoder']
        preprocessor.scaler = state['scaler']
        preprocessor.feature_cols = state['feature_cols']

        print(f"Preprocessor loaded from {filepath}")
        return preprocessor


def main():
    """Example usage"""
    print("="*60)
    print("BETH Autoencoder - Data Preprocessing")
    print("="*60)

    # Load data
    print("\n1. Loading data...")
    train_df = pd.read_csv('../Beta dataset/labelled_training_data.csv')
    test_df = pd.read_csv('../Beta dataset/labelled_testing_data.csv')

    print(f"Training data: {train_df.shape}")
    print(f"Test data: {test_df.shape}")

    # Create preprocessor
    print("\n2. Creating preprocessor...")
    preprocessor = SequencePreprocessor(sequence_length=50, stride=25)

    # Process training data
    print("\n3. Processing training data...")
    X_train, y_train, train_metadata = preprocessor.create_sequences(train_df, fit_encoders=True)
    X_train_scaled = preprocessor.scale_sequences(X_train, fit=True)

    # Process test data
    print("\n4. Processing test data...")
    X_test, y_test, test_metadata = preprocessor.create_sequences(test_df, fit_encoders=False)
    X_test_scaled = preprocessor.scale_sequences(X_test, fit=False)

    print(f"\nTraining sequences: {X_train_scaled.shape}")
    print(f"Test sequences: {X_test_scaled.shape}")

    # Label distribution
    print(f"\nTraining - Evil sequences: {y_train.sum()} ({y_train.mean()*100:.2f}%)")
    print(f"Test - Evil sequences: {y_test.sum()} ({y_test.mean()*100:.2f}%)")

    # For unsupervised learning, use only benign sequences
    X_train_benign = X_train_scaled[y_train == 0]
    print(f"\nBenign training sequences (for unsupervised learning): {X_train_benign.shape}")

    # Save preprocessed data
    print("\n5. Saving preprocessed data...")
    np.save('X_train_scaled.npy', X_train_scaled)
    np.save('y_train.npy', y_train)
    np.save('X_test_scaled.npy', X_test_scaled)
    np.save('y_test.npy', y_test)
    np.save('X_train_benign.npy', X_train_benign)

    with open('train_metadata.pkl', 'wb') as f:
        pickle.dump(train_metadata, f)
    with open('test_metadata.pkl', 'wb') as f:
        pickle.dump(test_metadata, f)

    preprocessor.save('preprocessor.pkl')

    print("\n✓ Preprocessing complete!")
    print("\nSaved files:")
    print("  - X_train_scaled.npy, y_train.npy")
    print("  - X_test_scaled.npy, y_test.npy")
    print("  - X_train_benign.npy")
    print("  - train_metadata.pkl, test_metadata.pkl")
    print("  - preprocessor.pkl")


if __name__ == '__main__':
    main()
