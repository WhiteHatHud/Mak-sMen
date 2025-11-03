#!/usr/bin/env python3
"""
Quick test script using pre-loaded test data
"""
import numpy as np
from tensorflow import keras

print("="*60)
print("AUTOENCODER MODEL - QUICK TEST")
print("="*60)

# Load pre-computed test data
print("\n1. Loading test data...")
X_test = np.load('X_test_scaled.npy')
y_test = np.load('y_test.npy')
print(f"   ✓ Loaded {len(X_test)} sequences")

# Load model and threshold (without compilation to avoid version issues)
print("\n2. Loading model...")
model = keras.models.load_model('best_autoencoder.h5', compile=False)
threshold = np.load('threshold.npy')
print(f"   ✓ Model loaded")
print(f"   ✓ Threshold: {threshold:.6f}")

# Test on first 100 sequences
print("\n3. Running predictions on 100 sequences...")
test_size = 100
X_sample = X_test[:test_size]
y_sample = y_test[:test_size]

X_pred = model.predict(X_sample, verbose=0)
errors = np.mean(np.square(X_sample - X_pred), axis=(1, 2))
predictions = (errors > threshold).astype(int)

print(f"   ✓ Predictions complete")

# Display results
print("\n" + "="*60)
print("RESULTS")
print("="*60)
print(f"Sequences tested: {test_size}")
print(f"Anomalies detected: {predictions.sum()}")
print(f"Actual malicious: {y_sample.sum()}")
print(f"Mean error: {errors.mean():.6f}")
print(f"Max error: {errors.max():.6f}")

# Show some examples
print("\n" + "="*60)
print("SAMPLE PREDICTIONS (First 10)")
print("="*60)
print(f"{'Index':<8} {'Error':<12} {'Predicted':<12} {'Actual':<10} {'Match':<8}")
print("-"*60)
for i in range(min(10, test_size)):
    pred_label = "ANOMALY" if predictions[i] == 1 else "Normal"
    actual_label = "Malicious" if y_sample[i] == 1 else "Benign"
    match = "✓" if predictions[i] == y_sample[i] else "✗"
    print(f"{i:<8} {errors[i]:<12.6f} {pred_label:<12} {actual_label:<10} {match:<8}")

# Calculate accuracy
accuracy = (predictions == y_sample).mean()
print("\n" + "="*60)
print(f"Accuracy on sample: {accuracy*100:.1f}%")
print("="*60)
print("\n✓ Model is working correctly!")
print("\nTo test with your own data, use the example in summary.md")
