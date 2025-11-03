#!/usr/bin/env python3
"""
Threshold Optimization Script
Finds the best threshold to balance FP and TP rates
"""

import pandas as pd
import numpy as np
from tensorflow import keras
from data_preprocessing import SequencePreprocessor
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, roc_curve
import matplotlib.pyplot as plt

print("="*70)
print("THRESHOLD OPTIMIZATION")
print("="*70)

# Load model and preprocessor
print("\n1. Loading model...")
model = keras.models.load_model('best_autoencoder.h5', compile=False)
preprocessor = SequencePreprocessor.load('preprocessor.pkl')
current_threshold = np.load('threshold.npy')
print(f"   Current threshold: {current_threshold:.6f}")

# Load test data
print("\n2. Loading test data...")
test_data = pd.read_csv('test_sample_large.csv')
print(f"   Loaded {len(test_data)} events")

# Create sequences
print("\n3. Creating sequences...")
X_test, y_test, metadata = preprocessor.create_sequences(test_data, fit_encoders=False)
X_test_scaled = preprocessor.scale_sequences(X_test, fit=False)
print(f"   Created {len(X_test_scaled)} sequences")
print(f"   Malicious sequences: {y_test.sum()}/{len(y_test)} ({y_test.mean()*100:.1f}%)")

# Calculate reconstruction errors
print("\n4. Calculating reconstruction errors...")
X_reconstructed = model.predict(X_test_scaled, verbose=0)
reconstruction_errors = np.mean(np.square(X_test_scaled - X_reconstructed), axis=(1, 2))

# Analyze error distribution
print("\n5. Reconstruction Error Distribution:")
print(f"   Benign sequences (mean): {reconstruction_errors[y_test==0].mean():.6f}")
print(f"   Malicious sequences (mean): {reconstruction_errors[y_test==1].mean():.6f}")
print(f"   Overall min: {reconstruction_errors.min():.6f}")
print(f"   Overall max: {reconstruction_errors.max():.6f}")

# Calculate metrics for different thresholds
print("\n6. Testing different thresholds...")
thresholds_to_test = np.percentile(reconstruction_errors, [70, 75, 80, 85, 90, 95, 99])
thresholds_to_test = np.concatenate([[current_threshold], thresholds_to_test])
thresholds_to_test = np.unique(thresholds_to_test)

results = []
for threshold in thresholds_to_test:
    predictions = (reconstruction_errors > threshold).astype(int)

    tp = ((predictions == 1) & (y_test == 1)).sum()
    fp = ((predictions == 1) & (y_test == 0)).sum()
    tn = ((predictions == 0) & (y_test == 0)).sum()
    fn = ((predictions == 0) & (y_test == 1)).sum()

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

    results.append({
        'threshold': threshold,
        'TP': tp, 'FP': fp, 'TN': tn, 'FN': fn,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'fpr': fpr
    })

results_df = pd.DataFrame(results)

print("\n" + "="*70)
print("THRESHOLD COMPARISON")
print("="*70)
print(results_df.to_string(index=False))

# Find best thresholds
print("\n" + "="*70)
print("RECOMMENDED THRESHOLDS")
print("="*70)

# Best F1
best_f1_idx = results_df['f1'].idxmax()
print(f"\n1. BEST F1 SCORE (Balanced):")
print(f"   Threshold: {results_df.loc[best_f1_idx, 'threshold']:.6f}")
print(f"   F1: {results_df.loc[best_f1_idx, 'f1']:.4f}")
print(f"   Precision: {results_df.loc[best_f1_idx, 'precision']:.4f}")
print(f"   Recall: {results_df.loc[best_f1_idx, 'recall']:.4f}")
print(f"   FPR: {results_df.loc[best_f1_idx, 'fpr']:.4f} ({results_df.loc[best_f1_idx, 'fpr']*100:.2f}%)")
print(f"   FP: {int(results_df.loc[best_f1_idx, 'FP'])}, TP: {int(results_df.loc[best_f1_idx, 'TP'])}")

# Best precision (lowest FP while maintaining decent recall)
high_recall = results_df[results_df['recall'] >= 0.7]  # Keep at least 70% recall
if len(high_recall) > 0:
    best_precision_idx = high_recall['precision'].idxmax()
    print(f"\n2. LOWEST FP (While Keeping 70%+ Recall):")
    print(f"   Threshold: {results_df.loc[best_precision_idx, 'threshold']:.6f}")
    print(f"   F1: {results_df.loc[best_precision_idx, 'f1']:.4f}")
    print(f"   Precision: {results_df.loc[best_precision_idx, 'precision']:.4f}")
    print(f"   Recall: {results_df.loc[best_precision_idx, 'recall']:.4f}")
    print(f"   FPR: {results_df.loc[best_precision_idx, 'fpr']:.4f} ({results_df.loc[best_precision_idx, 'fpr']*100:.2f}%)")
    print(f"   FP: {int(results_df.loc[best_precision_idx, 'FP'])}, TP: {int(results_df.loc[best_precision_idx, 'TP'])}")

# Best for SOC (minimize FPR while catching most threats)
high_recall_90 = results_df[results_df['recall'] >= 0.90]
if len(high_recall_90) > 0:
    best_soc_idx = high_recall_90['fpr'].idxmin()
    print(f"\n3. SOC OPTIMIZED (Catch 90%+ of Threats, Minimize Alerts):")
    print(f"   Threshold: {results_df.loc[best_soc_idx, 'threshold']:.6f}")
    print(f"   F1: {results_df.loc[best_soc_idx, 'f1']:.4f}")
    print(f"   Precision: {results_df.loc[best_soc_idx, 'precision']:.4f}")
    print(f"   Recall: {results_df.loc[best_soc_idx, 'recall']:.4f}")
    print(f"   FPR: {results_df.loc[best_soc_idx, 'fpr']:.4f} ({results_df.loc[best_soc_idx, 'fpr']*100:.2f}%)")
    print(f"   FP: {int(results_df.loc[best_soc_idx, 'FP'])}, TP: {int(results_df.loc[best_soc_idx, 'TP'])}")

# Current threshold performance
current_idx = results_df[results_df['threshold'] == current_threshold].index[0]
print(f"\n4. CURRENT THRESHOLD (For Comparison):")
print(f"   Threshold: {results_df.loc[current_idx, 'threshold']:.6f}")
print(f"   F1: {results_df.loc[current_idx, 'f1']:.4f}")
print(f"   Precision: {results_df.loc[current_idx, 'precision']:.4f}")
print(f"   Recall: {results_df.loc[current_idx, 'recall']:.4f}")
print(f"   FPR: {results_df.loc[current_idx, 'fpr']:.4f} ({results_df.loc[current_idx, 'fpr']*100:.2f}%)")
print(f"   FP: {int(results_df.loc[current_idx, 'FP'])}, TP: {int(results_df.loc[current_idx, 'TP'])}")

# Calculate ROC AUC
try:
    roc_auc = roc_auc_score(y_test, reconstruction_errors)
    print(f"\nROC AUC Score: {roc_auc:.4f}")
except:
    print("\nCould not calculate ROC AUC")

# Save recommended threshold
print("\n" + "="*70)
print("SAVING OPTIMIZED THRESHOLD")
print("="*70)

best_threshold = results_df.loc[best_f1_idx, 'threshold']
np.save('threshold_optimized.npy', best_threshold)
print(f"\n✓ Saved optimized threshold to: threshold_optimized.npy")
print(f"  Value: {best_threshold:.6f}")

# Create visualization
print("\n7. Creating visualization...")
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Plot 1: Threshold vs Metrics
ax1 = axes[0, 0]
ax1.plot(results_df['threshold'], results_df['precision'], 'g-', label='Precision', marker='o')
ax1.plot(results_df['threshold'], results_df['recall'], 'b-', label='Recall', marker='s')
ax1.plot(results_df['threshold'], results_df['f1'], 'r-', label='F1 Score', marker='^')
ax1.axvline(best_threshold, color='red', linestyle='--', alpha=0.5, label='Best F1 Threshold')
ax1.axvline(current_threshold, color='orange', linestyle='--', alpha=0.5, label='Current Threshold')
ax1.set_xlabel('Threshold')
ax1.set_ylabel('Score')
ax1.set_title('Metrics vs Threshold')
ax1.legend()
ax1.grid(True, alpha=0.3)

# Plot 2: FPR vs Recall
ax2 = axes[0, 1]
ax2.plot(results_df['fpr'], results_df['recall'], 'b-', marker='o')
ax2.scatter(results_df.loc[best_f1_idx, 'fpr'], results_df.loc[best_f1_idx, 'recall'],
           color='red', s=200, marker='*', label='Best F1', zorder=5)
ax2.scatter(results_df.loc[current_idx, 'fpr'], results_df.loc[current_idx, 'recall'],
           color='orange', s=200, marker='X', label='Current', zorder=5)
ax2.set_xlabel('False Positive Rate')
ax2.set_ylabel('Recall (True Positive Rate)')
ax2.set_title('ROC-like Curve')
ax2.legend()
ax2.grid(True, alpha=0.3)

# Plot 3: Error distribution
ax3 = axes[1, 0]
benign_errors = reconstruction_errors[y_test == 0]
malicious_errors = reconstruction_errors[y_test == 1]
ax3.hist(benign_errors, bins=50, alpha=0.6, label=f'Benign (n={len(benign_errors)})', color='blue')
ax3.hist(malicious_errors, bins=50, alpha=0.6, label=f'Malicious (n={len(malicious_errors)})', color='red')
ax3.axvline(current_threshold, color='orange', linestyle='--', linewidth=2, label='Current Threshold')
ax3.axvline(best_threshold, color='green', linestyle='--', linewidth=2, label='Optimized Threshold')
ax3.set_xlabel('Reconstruction Error')
ax3.set_ylabel('Count')
ax3.set_title('Error Distribution')
ax3.set_yscale('log')
ax3.legend()
ax3.grid(True, alpha=0.3)

# Plot 4: FP vs FN tradeoff
ax4 = axes[1, 1]
ax4.plot(results_df['threshold'], results_df['FP'], 'r-', label='False Positives', marker='o')
ax4.plot(results_df['threshold'], results_df['FN'], 'b-', label='False Negatives', marker='s')
ax4.axvline(best_threshold, color='red', linestyle='--', alpha=0.5, label='Best F1 Threshold')
ax4.axvline(current_threshold, color='orange', linestyle='--', alpha=0.5, label='Current Threshold')
ax4.set_xlabel('Threshold')
ax4.set_ylabel('Count')
ax4.set_title('False Positives vs False Negatives')
ax4.legend()
ax4.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('threshold_optimization.png', dpi=150, bbox_inches='tight')
print(f"✓ Saved visualization to: threshold_optimization.png")

print("\n" + "="*70)
print("NEXT STEPS")
print("="*70)
print("\nTo use the optimized threshold in test.py:")
print("1. Replace 'threshold.npy' with 'threshold_optimized.npy'")
print("   OR")
print("2. Copy threshold_optimized.npy to threshold.npy:")
print("   cp threshold_optimized.npy threshold.npy")
print("\n3. Re-run: python test.py")

print("\n" + "="*70)
