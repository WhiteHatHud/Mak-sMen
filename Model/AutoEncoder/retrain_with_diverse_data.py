#!/usr/bin/env python3
"""
Retrain Model with More Diverse Benign Data
This reduces FP by teaching the model about ALL normal behaviors
"""

import pandas as pd
import numpy as np
from data_preprocessing import SequencePreprocessor
from autoencoder_model import create_autoencoder
from tensorflow import keras
import matplotlib.pyplot as plt

print("="*70)
print("RETRAINING WITH DIVERSE BENIGN DATA")
print("="*70)

# Step 1: Load training data + validation data for more diversity
print("\n1. Loading diverse training data...")
train_data = pd.read_csv('../Beta dataset/labelled_training_data.csv')
val_data = pd.read_csv('../Beta dataset/labelled_validation_data.csv')

# Combine and keep only benign
combined = pd.concat([train_data, val_data], ignore_index=True)
benign_data = combined[combined['evil'] == 0].copy()

print(f"   Training data: {len(train_data)} events")
print(f"   Validation data: {len(val_data)} events")
print(f"   Combined benign: {len(benign_data)} events")
print(f"   Unique processes: {benign_data['processId'].nunique()}")
print(f"   Unique hosts: {benign_data['hostName'].nunique()}")

# Step 2: Create preprocessor with new data
print("\n2. Creating sequences from diverse benign data...")
preprocessor = SequencePreprocessor(sequence_length=50)
X_train, y_train, metadata = preprocessor.create_sequences(benign_data)

# Filter to only benign sequences
benign_mask = y_train == 0
X_train_benign = X_train[benign_mask]
print(f"   Created {len(X_train_benign)} benign sequences")

# Scale
X_train_scaled = preprocessor.scale_sequences(X_train_benign, fit=True)

# Step 3: Train model
print("\n3. Training autoencoder...")
input_shape = X_train_scaled.shape[1:]
model = create_autoencoder(input_shape, encoding_dim=32)

# Compile
model.compile(optimizer='adam', loss='mse')

# Early stopping
early_stop = keras.callbacks.EarlyStopping(
    monitor='val_loss',
    patience=5,
    restore_best_weights=True
)

# Train with validation split
history = model.fit(
    X_train_scaled, X_train_scaled,
    epochs=50,
    batch_size=32,
    validation_split=0.2,
    callbacks=[early_stop],
    verbose=1
)

# Step 4: Calculate new threshold on training data
print("\n4. Calculating new threshold...")
X_reconstructed = model.predict(X_train_scaled, verbose=0)
train_mse = np.mean(np.square(X_train_scaled - X_reconstructed), axis=(1, 2))

# Use 95th percentile as threshold (captures 95% of normal behavior)
new_threshold = np.percentile(train_mse, 95)
print(f"   New threshold (95th percentile): {new_threshold:.6f}")
print(f"   Mean train error: {train_mse.mean():.6f}")
print(f"   Max train error: {train_mse.max():.6f}")

# Step 5: Save
print("\n5. Saving improved model...")
model.save('best_autoencoder_diverse.h5')
preprocessor.save('preprocessor_diverse.pkl')
np.save('threshold_diverse.npy', new_threshold)

print("\n✓ Saved:")
print("  - best_autoencoder_diverse.h5")
print("  - preprocessor_diverse.pkl")
print("  - threshold_diverse.npy")

# Step 6: Quick test on test data
print("\n6. Quick validation on test data...")
test_data = pd.read_csv('test_sample_large.csv')
X_test, y_test, _ = preprocessor.create_sequences(test_data, fit_encoders=False)
X_test_scaled = preprocessor.scale_sequences(X_test, fit=False)

X_test_recon = model.predict(X_test_scaled, verbose=0)
test_errors = np.mean(np.square(X_test_scaled - X_test_recon), axis=(1, 2))

predictions = (test_errors > new_threshold).astype(int)

tp = ((predictions == 1) & (y_test == 1)).sum()
fp = ((predictions == 1) & (y_test == 0)).sum()
tn = ((predictions == 0) & (y_test == 0)).sum()
fn = ((predictions == 0) & (y_test == 1)).sum()

precision = tp / (tp + fp) if (tp + fp) > 0 else 0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

print("\nNew Model Performance:")
print(f"  Precision: {precision:.4f} ({precision*100:.2f}%)")
print(f"  Recall: {recall:.4f} ({recall*100:.2f}%)")
print(f"  F1 Score: {f1:.4f}")
print(f"  FPR: {fpr:.4f} ({fpr*100:.2f}%)")
print(f"  FP: {fp}, TP: {tp}, FN: {fn}, TN: {tn}")

print("\n" + "="*70)
print("TO USE THE IMPROVED MODEL:")
print("="*70)
print("\nOption 1 - Replace existing files:")
print("  cp best_autoencoder_diverse.h5 best_autoencoder.h5")
print("  cp preprocessor_diverse.pkl preprocessor.pkl")
print("  cp threshold_diverse.npy threshold.npy")
print("  python test.py")
print("\nOption 2 - Edit test.py to use _diverse files")
print("="*70)
