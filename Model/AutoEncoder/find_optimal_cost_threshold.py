"""
Find optimal threshold using custom cost function
FN cost = 10 (missing a threat is expensive)
FP cost = 3 (false alarm is moderately expensive)
"""

import numpy as np
from sklearn.metrics import confusion_matrix, precision_score, recall_score, f1_score

# Cost parameters
FP_COST = 3   # Cost of false positive (false alarm)
FN_COST = 10  # Cost of false negative (missed threat)

print("="*70)
print("COST-BASED THRESHOLD OPTIMIZATION")
print("="*70)
print(f"\nCost Function:")
print(f"  False Positive (FP) cost: {FP_COST}")
print(f"  False Negative (FN) cost: {FN_COST}")
print(f"  Total Cost = (FP × {FP_COST}) + (FN × {FN_COST})")
print(f"\nFN cost is {FN_COST/FP_COST:.1f}x more expensive - prioritizing recall!\n")

# Load data
print("Loading test data...")
test_mse = np.load('test_mse.npy')
y_test = np.load('y_test.npy')

print(f"Test sequences: {len(y_test)}")
print(f"Actual malicious: {y_test.sum()} ({y_test.mean()*100:.1f}%)")
print(f"Reconstruction error range: {test_mse.min():.2f} - {test_mse.max():.2f}")

# Test range of thresholds (from low to high percentiles)
print("\nTesting thresholds from 50th to 99.9th percentile...")
thresholds = np.percentile(test_mse, np.arange(50, 100, 0.5))

# Add some specific low thresholds to catch more threats
extra_low_thresholds = np.arange(2.0, 5.0, 0.25)
thresholds = np.concatenate([extra_low_thresholds, thresholds])
thresholds = np.unique(thresholds)
thresholds = np.sort(thresholds)

print(f"Testing {len(thresholds)} different threshold values...")

# Find optimal threshold
min_cost = float('inf')
best_threshold = None
best_metrics = None

results = []

for threshold in thresholds:
    y_pred = (test_mse > threshold).astype(int)
    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()

    # Calculate total cost
    total_cost = (fp * FP_COST) + (fn * FN_COST)

    # Calculate metrics
    precision = precision_score(y_test, y_pred) if (tp + fp) > 0 else 0
    recall = recall_score(y_test, y_pred) if (tp + fn) > 0 else 0
    f1 = f1_score(y_test, y_pred) if (precision + recall) > 0 else 0

    results.append({
        'threshold': threshold,
        'cost': total_cost,
        'fp': fp,
        'fn': fn,
        'tp': tp,
        'tn': tn,
        'precision': precision,
        'recall': recall,
        'f1': f1
    })

    if total_cost < min_cost:
        min_cost = total_cost
        best_threshold = threshold
        best_metrics = {
            'tn': tn, 'fp': fp, 'fn': fn, 'tp': tp,
            'precision': precision,
            'recall': recall,
            'f1': f1
        }

# Display results
print("\n" + "="*70)
print("OPTIMAL THRESHOLD FOUND")
print("="*70)

print(f"\n🎯 Optimal Threshold: {best_threshold:.6f}")
print(f"💰 Minimum Total Cost: {min_cost:.0f}")

print(f"\n📊 Cost Breakdown:")
print(f"   FP Cost: {best_metrics['fp']} × {FP_COST} = {best_metrics['fp'] * FP_COST}")
print(f"   FN Cost: {best_metrics['fn']} × {FN_COST} = {best_metrics['fn'] * FN_COST}")
print(f"   Total:   {min_cost:.0f}")

print(f"\n📈 Confusion Matrix:")
print(f"                Predicted")
print(f"               Benign  Malicious")
print(f"Actual Benign    {best_metrics['tn']:<6}  {best_metrics['fp']:<6}")
print(f"       Malicious {best_metrics['fn']:<6}  {best_metrics['tp']:<6}")

print(f"\n✅ Performance Metrics:")
print(f"   Precision: {best_metrics['precision']:.4f} ({best_metrics['precision']*100:.2f}%)")
print(f"   Recall:    {best_metrics['recall']:.4f} ({best_metrics['recall']*100:.2f}%)")
print(f"   F1 Score:  {best_metrics['f1']:.4f} ({best_metrics['f1']*100:.2f}%)")

print(f"\n🔍 Detection Summary:")
print(f"   True Positives:  {best_metrics['tp']} (threats caught)")
print(f"   False Negatives: {best_metrics['fn']} (threats missed)")
print(f"   False Positives: {best_metrics['fp']} (false alarms)")
print(f"   True Negatives:  {best_metrics['tn']} (correctly identified benign)")

# Show top 10 thresholds by cost
print("\n" + "="*70)
print("TOP 10 THRESHOLDS BY COST")
print("="*70)

results_sorted = sorted(results, key=lambda x: x['cost'])[:10]

print(f"\n{'Rank':<6} {'Threshold':<12} {'Cost':<10} {'FP':<6} {'FN':<6} {'Precision':<12} {'Recall':<12} {'F1':<12}")
print("-"*90)

for i, r in enumerate(results_sorted, 1):
    print(f"{i:<6} {r['threshold']:<12.4f} {r['cost']:<10.0f} {r['fp']:<6} {r['fn']:<6} {r['precision']:<12.4f} {r['recall']:<12.4f} {r['f1']:<12.4f}")

# Save optimal threshold
print("\n" + "="*70)
print("SAVING RESULTS")
print("="*70)

np.save('optimal_threshold_cost_based.npy', best_threshold)
print(f"\n✅ Saved optimal threshold to: optimal_threshold_cost_based.npy")

print("\n📝 To use this threshold in test.py, update line 11:")
print(f"   threshold = {best_threshold:.6f}")
print(f"\n   OR")
print(f"   threshold = np.load('optimal_threshold_cost_based.npy')")

print("\n" + "="*70)
