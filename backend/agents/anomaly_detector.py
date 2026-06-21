"""
Anomaly Detector — ML-based anomaly detection on query results

Uses:
- Isolation Forest (sklearn) — primary detector
- Z-score — secondary signal
- Ensemble: flag if either method detects anomaly

Resume talking point:
"Isolation Forest + Z-score ensemble anomaly detection on query results
with LLM-generated severity explanations"
"""
from dataclasses import dataclass, field
from typing import List, Optional
import structlog

log = structlog.get_logger()


@dataclass
class AnomalyResult:
    index: int
    value: float
    label: Optional[str]  # x-axis label (date, category, etc.)
    z_score: float
    isolation_score: float
    severity: str  # "high" | "medium" | "low"
    is_anomaly: bool


@dataclass
class DetectionResult:
    anomalies: List[AnomalyResult] = field(default_factory=list)
    total_points: int = 0
    anomaly_count: int = 0
    mean: float = 0.0
    std: float = 0.0
    method: str = "isolation_forest+zscore"
    error: Optional[str] = None


class AnomalyDetector:
    """
    Detects anomalies in a list of numeric values.
    Works on any query result that has a numeric column.
    """

    def detect(
        self,
        values: List[float],
        labels: List[str] = None,
        contamination: float = 0.1,
    ) -> DetectionResult:

        if len(values) < 4:
            return DetectionResult(
                error="Need at least 4 data points for anomaly detection",
                total_points=len(values),
            )

        try:
            import numpy as np
            from sklearn.ensemble import IsolationForest

            X = np.array(values, dtype=float).reshape(-1, 1)
            mean = float(np.mean(X))
            std = float(np.std(X))

            # Isolation Forest
            iso = IsolationForest(
                contamination=contamination,
                random_state=42,
                n_estimators=100,
            )
            iso_labels = iso.fit_predict(X)  # -1 = anomaly
            iso_scores = iso.score_samples(X)  # lower = more anomalous

            # Z-scores
            if std > 0:
                z_scores = np.abs((X - mean) / std).flatten()
            else:
                z_scores = np.zeros(len(values))

            anomalies = []
            for i, (val, iso_label, iso_score, z) in enumerate(
                zip(values, iso_labels, iso_scores, z_scores)
            ):
                is_anomaly = iso_label == -1 or float(z) > 2.5

                if is_anomaly:
                    severity = "high" if float(z) > 3.0 else "medium" if float(z) > 2.0 else "low"
                    anomalies.append(AnomalyResult(
                        index=i,
                        value=float(val),
                        label=labels[i] if labels and i < len(labels) else str(i),
                        z_score=round(float(z), 3),
                        isolation_score=round(float(iso_score), 4),
                        severity=severity,
                        is_anomaly=True,
                    ))

            return DetectionResult(
                anomalies=anomalies,
                total_points=len(values),
                anomaly_count=len(anomalies),
                mean=round(mean, 4),
                std=round(std, 4),
                method="isolation_forest+zscore",
            )

        except ImportError:
            return DetectionResult(
                error="sklearn not installed. Run: pip install scikit-learn",
            )
        except Exception as e:
            log.error("anomaly_detection_failed", error=str(e))
            return DetectionResult(error=str(e))

    def detect_from_query_result(
        self,
        columns: List[str],
        rows: List[list],
        value_col: str = None,
        label_col: str = None,
    ) -> DetectionResult:
        """
        Auto-detect numeric column from query results and run anomaly detection.
        If value_col not specified, picks first numeric column.
        """
        if not columns or not rows:
            return DetectionResult(error="No data to analyze")

        # Find numeric column
        col_idx = None
        if value_col and value_col in columns:
            col_idx = columns.index(value_col)
        else:
            # Auto-pick first numeric column
            for i, col in enumerate(columns):
                try:
                    float(rows[0][i])
                    col_idx = i
                    break
                except (ValueError, TypeError, IndexError):
                    continue

        if col_idx is None:
            return DetectionResult(error="No numeric column found for anomaly detection")

        # Find label column
        label_idx = None
        if label_col and label_col in columns:
            label_idx = columns.index(label_col)
        else:
            # Use first non-numeric column as label
            for i, col in enumerate(columns):
                if i != col_idx:
                    label_idx = i
                    break

        values = []
        labels = []
        for row in rows:
            try:
                values.append(float(row[col_idx]))
                labels.append(str(row[label_idx]) if label_idx is not None else str(len(values)))
            except (ValueError, TypeError):
                continue

        return self.detect(values, labels)
