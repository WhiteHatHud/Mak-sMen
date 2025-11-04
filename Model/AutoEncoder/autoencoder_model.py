"""
Autoencoder Model Architecture and Training
For unsupervised anomaly detection in system call sequences
"""

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, Model
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
import matplotlib.pyplot as plt
import seaborn as sns


def build_autoencoder(sequence_length, n_features, encoding_dim=16):
    """
    Build a deep autoencoder for sequence reconstruction.

    Architecture:
    - Encoder: Compresses sequences into latent representation
    - Decoder: Reconstructs sequences from latent representation
    - Anomalies will have higher reconstruction error

    Args:
        sequence_length: Length of input sequences
        n_features: Number of features per timestep
        encoding_dim: Dimension of latent encoding

    Returns:
        autoencoder: Keras Model
    """

    # Input layer
    input_layer = layers.Input(shape=(sequence_length, n_features), name='input')

    # Encoder
    x = layers.Dense(128, activation='relu', name='encoder_1')(input_layer)
    x = layers.Dropout(0.2)(x)
    x = layers.Dense(64, activation='relu', name='encoder_2')(x)
    x = layers.Dropout(0.2)(x)
    encoded = layers.Dense(encoding_dim, activation='relu', name='encoding')(x)

    # Decoder
    x = layers.Dense(64, activation='relu', name='decoder_1')(encoded)
    x = layers.Dropout(0.2)(x)
    x = layers.Dense(128, activation='relu', name='decoder_2')(x)
    x = layers.Dropout(0.2)(x)
    decoded = layers.Dense(n_features, activation='linear', name='output')(x)

    # Create model
    autoencoder = Model(inputs=input_layer, outputs=decoded, name='autoencoder')

    # Compile
    autoencoder.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss='mse',
        metrics=['mae']
    )

    return autoencoder


def train_autoencoder(autoencoder, X_train, epochs=50, batch_size=256, validation_split=0.2):
    """
    Train autoencoder on benign sequences only (unsupervised).

    Args:
        autoencoder: Keras model
        X_train: Training sequences (benign only)
        epochs: Number of training epochs
        batch_size: Batch size
        validation_split: Validation data proportion

    Returns:
        history: Training history
    """

    # Callbacks
    early_stopping = EarlyStopping(
        monitor='val_loss',
        patience=10,
        restore_best_weights=True,
        verbose=1
    )

    reduce_lr = ReduceLROnPlateau(
        monitor='val_loss',
        factor=0.5,
        patience=5,
        min_lr=1e-6,
        verbose=1
    )

    checkpoint = ModelCheckpoint(
        'best_autoencoder.h5',
        monitor='val_loss',
        save_best_only=True,
        verbose=1
    )

    print("Training autoencoder on benign sequences...")
    print(f"Input shape: {X_train.shape}")
    print(f"Epochs: {epochs}, Batch size: {batch_size}\n")

    # Train (target is same as input for reconstruction)
    history = autoencoder.fit(
        X_train,
        X_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=validation_split,
        callbacks=[early_stopping, reduce_lr, checkpoint],
        verbose=1
    )

    print("\nTraining complete!")

    return history


def calculate_reconstruction_errors(autoencoder, X, batch_size=256):
    """
    Calculate reconstruction error (MSE) for each sequence.

    Args:
        autoencoder: Trained Keras model
        X: Input sequences
        batch_size: Batch size for prediction

    Returns:
        Array of MSE values (one per sequence)
    """
    print(f"Calculating reconstruction errors for {len(X)} sequences...")

    X_pred = autoencoder.predict(X, batch_size=batch_size, verbose=1)
    mse = np.mean(np.square(X - X_pred), axis=(1, 2))

    print(f"MSE - Mean: {mse.mean():.4f}, Std: {mse.std():.4f}")

    return mse


def determine_threshold(train_mse, percentile=95):
    """
    Determine anomaly threshold from training reconstruction errors.

    Args:
        train_mse: Training set reconstruction errors
        percentile: Percentile to use as threshold

    Returns:
        threshold value
    """
    threshold = np.percentile(train_mse, percentile)
    print(f"Anomaly threshold: {threshold:.4f} ({percentile}th percentile)")
    return threshold


def plot_training_history(history, save_path='training_history.png'):
    """Plot training and validation loss."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 5))

    # Loss
    axes[0].plot(history.history['loss'], label='Training Loss', linewidth=2)
    axes[0].plot(history.history['val_loss'], label='Validation Loss', linewidth=2)
    axes[0].set_xlabel('Epoch', fontsize=12)
    axes[0].set_ylabel('Loss (MSE)', fontsize=12)
    axes[0].set_title('Autoencoder Training Loss', fontsize=14, fontweight='bold')
    axes[0].legend(fontsize=11)
    axes[0].grid(alpha=0.3)

    # MAE
    axes[1].plot(history.history['mae'], label='Training MAE', linewidth=2)
    axes[1].plot(history.history['val_mae'], label='Validation MAE', linewidth=2)
    axes[1].set_xlabel('Epoch', fontsize=12)
    axes[1].set_ylabel('MAE', fontsize=12)
    axes[1].set_title('Mean Absolute Error', fontsize=14, fontweight='bold')
    axes[1].legend(fontsize=11)
    axes[1].grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()

    print(f"Training history plot saved to {save_path}")


def plot_reconstruction_error_distribution(train_mse, test_mse, y_test, threshold,
                                            save_path='reconstruction_error_dist.png'):
    """Plot distribution of reconstruction errors."""
    test_benign_mse = test_mse[y_test == 0]
    test_malicious_mse = test_mse[y_test == 1]

    plt.figure(figsize=(14, 6))

    plt.hist(test_benign_mse, bins=100, alpha=0.6,
             label=f'Benign (n={len(test_benign_mse)})', color='green')
    plt.hist(test_malicious_mse, bins=100, alpha=0.6,
             label=f'Malicious (n={len(test_malicious_mse)})', color='red')
    plt.axvline(threshold, color='black', linestyle='--',
                linewidth=2, label=f'Threshold={threshold:.3f}')

    plt.xlabel('Reconstruction Error (MSE)', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title('Reconstruction Error Distribution - Test Set', fontsize=14, fontweight='bold')
    plt.legend(fontsize=11)
    plt.yscale('log')
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()

    print(f"\nError distribution plot saved to {save_path}")
    print(f"Benign MSE - Mean: {test_benign_mse.mean():.4f}, Median: {np.median(test_benign_mse):.4f}")
    print(f"Malicious MSE - Mean: {test_malicious_mse.mean():.4f}, Median: {np.median(test_malicious_mse):.4f}")


def main():
    """Main training pipeline"""
    print("="*60)
    print("BETH Autoencoder - Model Training")
    print("="*60)

    # Load preprocessed data
    print("\n1. Loading preprocessed data...")
    X_train_scaled = np.load('X_train_scaled.npy')
    y_train = np.load('y_train.npy')
    X_test_scaled = np.load('X_test_scaled.npy')
    y_test = np.load('y_test.npy')
    X_train_benign = np.load('X_train_benign.npy')

    print(f"Training sequences: {X_train_scaled.shape}")
    print(f"Test sequences: {X_test_scaled.shape}")
    print(f"Benign training sequences: {X_train_benign.shape}")

    # Build model
    print("\n2. Building autoencoder...")
    sequence_length = X_train_scaled.shape[1]
    n_features = X_train_scaled.shape[2]

    autoencoder = build_autoencoder(sequence_length, n_features, encoding_dim=16)
    print("\nModel Architecture:")
    autoencoder.summary()

    # Train model
    print("\n3. Training autoencoder...")
    history = train_autoencoder(
        autoencoder,
        X_train_benign,
        epochs=50,
        batch_size=256,
        validation_split=0.2
    )

    # Plot training history
    print("\n4. Plotting training history...")
    plot_training_history(history)

    # Calculate reconstruction errors
    print("\n5. Calculating reconstruction errors...")
    train_mse = calculate_reconstruction_errors(autoencoder, X_train_scaled)
    test_mse = calculate_reconstruction_errors(autoencoder, X_test_scaled)

    # Determine threshold
    print("\n6. Determining anomaly threshold...")
    #threshold = 2.7383
    threshold = 7.7
    # Plot error distribution
    print("\n7. Plotting error distribution...")
    plot_reconstruction_error_distribution(train_mse, test_mse, y_test, threshold)

    # Make predictions
    print("\n8. Making predictions...")
    y_pred = (test_mse > threshold).astype(int)
    print(f"Predicted anomalies: {y_pred.sum()} ({y_pred.mean()*100:.2f}%)")
    print(f"Actual malicious: {y_test.sum()} ({y_test.mean()*100:.2f}%)")

    # Save results
    print("\n9. Saving results...")
    autoencoder.save('autoencoder_final.h5')
    np.save('train_mse.npy', train_mse)
    np.save('test_mse.npy', test_mse)
    np.save('y_pred.npy', y_pred)
    np.save('threshold.npy', threshold)

    print("\n Training complete!")
    print("\nSaved files:")
    print("  - autoencoder_final.h5 (trained model)")
    print("  - best_autoencoder.h5 (best checkpoint)")
    print("  - train_mse.npy, test_mse.npy (reconstruction errors)")
    print("  - y_pred.npy, threshold.npy")
    print("  - training_history.png")
    print("  - reconstruction_error_dist.png")


if __name__ == '__main__':
    main()
