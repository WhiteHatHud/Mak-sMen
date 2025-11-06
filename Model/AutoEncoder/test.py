import pandas as pd
import numpy as np
from tensorflow import keras
from data_preprocessing import SequencePreprocessor
from sklearn.metrics import confusion_matrix, precision_score, recall_score, f1_score

# 1. Load the trained model and preprocessor
print("Loading model...")
model = keras.models.load_model('backup_7.7.h5', compile=False)
preprocessor = SequencePreprocessor.load('preprocessor.pkl')
threshold = 3.0

print(f"Anomaly threshold: {threshold:.6f}")

# 2. Prepare your test data
# Your CSV should have these columns:
# - timestamp, hostName, processId, processName, eventName
# - userId, threadId, argsNum, returnValue, sus, evil

test_data = pd.read_csv('../Beta dataset/labelled_validation_data.csv')
print(f"Loaded {len(test_data)} system call events")

# 3. Preprocess the data
print("Preprocessing sequences...")
X_test, y_test, metadata = preprocessor.create_sequences(
    test_data,
    fit_encoders=False  # Use existing encoders
)
X_test_scaled = preprocessor.scale_sequences(X_test, fit=False)

print(f"Created {len(X_test_scaled)} sequences")

# 4. Calculate reconstruction errors
print("Calculating reconstruction errors...")
X_reconstructed = model.predict(X_test_scaled, verbose=0)
reconstruction_errors = np.mean(np.square(X_test_scaled - X_reconstructed), axis=(1, 2))

# 5. Detect anomalies
predictions = (reconstruction_errors > threshold).astype(int)
anomaly_count = predictions.sum()

print(f"\nResults:")
print(f"- Anomalies detected: {anomaly_count}/{len(predictions)} ({anomaly_count/len(predictions)*100:.1f}%)")
print(f"- Actual malicious: {y_test.sum()}/{len(y_test)} ({y_test.mean()*100:.1f}%)")
print(f"- Mean reconstruction error: {reconstruction_errors.mean():.6f}")
print(f"- Max reconstruction error: {reconstruction_errors.max():.6f}")

# Calculate performance metrics
print("\n" + "="*60)
print("PERFORMANCE METRICS")
print("="*60)

# Confusion Matrix
cm = confusion_matrix(y_test, predictions)
tn, fp, fn, tp = cm.ravel()

print("\nConfusion Matrix:")
print(f"                Predicted")
print(f"               Benign  Malicious")
print(f"Actual Benign    {tn:<6}  {fp:<6}")
print(f"       Malicious {fn:<6}  {tp:<6}")

print(f"\nBreakdown:")
print(f"  True Negatives (TN):  {tn:>4} - Correctly identified benign")
print(f"  False Positives (FP): {fp:>4} - Benign flagged as malicious")
print(f"  False Negatives (FN): {fn:>4} - Malicious missed")
print(f"  True Positives (TP):  {tp:>4} - Correctly identified malicious")

# Calculate metrics (handle division by zero)
if (tp + fp) > 0:
    precision = precision_score(y_test, predictions)
else:
    precision = 0.0

if (tp + fn) > 0:
    recall = recall_score(y_test, predictions)
else:
    recall = 0.0

if (precision + recall) > 0:
    f1 = f1_score(y_test, predictions)
else:
    f1 = 0.0

# Calculate rates
tpr = tp / (tp + fn) if (tp + fn) > 0 else 0  # True Positive Rate (Recall)
fpr = fp / (fp + tn) if (fp + tn) > 0 else 0  # False Positive Rate
tnr = tn / (tn + fp) if (tn + fp) > 0 else 0  # True Negative Rate (Specificity)

print("\n" + "="*60)
print("KEY METRICS")
print("="*60)
print(f"Precision:    {precision:.4f} ({precision*100:.2f}%)")
print(f"Recall (TPR): {recall:.4f} ({recall*100:.2f}%)")
print(f"F1 Score:     {f1:.4f}")
print(f"")
print(f"True Positive Rate (TPR):  {tpr:.4f} ({tpr*100:.2f}%)")
print(f"False Positive Rate (FPR): {fpr:.4f} ({fpr*100:.2f}%)")
print(f"Specificity (TNR):         {tnr:.4f} ({tnr*100:.2f}%)")
print("="*60)

# 6. Assign priorities to anomalies
if anomaly_count > 0:
    anomaly_indices = np.where(predictions == 1)[0]
    anomaly_errors = reconstruction_errors[anomaly_indices]

    # Calculate priority quartiles
    q75 = np.percentile(anomaly_errors, 75)
    q50 = np.percentile(anomaly_errors, 50)
    q25 = np.percentile(anomaly_errors, 25)

    priorities = []
    for error in anomaly_errors:
        if error >= q75:
            priorities.append('CRITICAL')
        elif error >= q50:
            priorities.append('HIGH')
        elif error >= q25:
            priorities.append('MEDIUM')
        else:
            priorities.append('LOW')

    # 7. Create results DataFrame with additional context
    # Extract process names from original data for better interpretability
    process_names = []
    for idx in anomaly_indices:
        meta = metadata[idx]
        # Find matching process in original data
        process_mask = (test_data['processId'] == meta['processId']) & \
                       (test_data['hostName'] == meta['hostName'])
        process_subset = test_data[process_mask]

        # Get process name if available
        if len(process_subset) > 0 and 'processName' in process_subset.columns:
            process_name = process_subset['processName'].mode()[0]
        else:
            process_name = 'unknown'

        process_names.append(process_name)

    results = pd.DataFrame({
        'sequence_index': anomaly_indices,
        'hostName': [metadata[i]['hostName'] for i in anomaly_indices],
        'processId': [metadata[i]['processId'] for i in anomaly_indices],
        'processName': process_names,
        'start_idx': [metadata[i]['start_idx'] for i in anomaly_indices],
        'reconstruction_error': anomaly_errors,
        'priority': priorities
    })

    # Sort by error (most critical first)
    results = results.sort_values('reconstruction_error', ascending=False)

    # 8. Display top threats
    print("\n" + "="*60)
    print("TOP 10 MOST CRITICAL ANOMALIES")
    print("="*60)
    print(results.head(10).to_string(index=False))

    # Save results
    results.to_csv('new_test_results.csv', index=False)
    print("\nFull results saved to: new_test_results.csv")
else:
    print("\nNo anomalies detected - all sequences appear normal!")