
from pathlib import Path
import sys
import pandas as pd
import joblib

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from segmentation import assign_segments

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python predict_segment.py new_customers.csv")
        raise SystemExit(2)
    input_path = Path(sys.argv[1])
    artifact = joblib.load(ROOT / "segment_model.joblib")
    df = pd.read_csv(input_path)
    out = assign_segments(df, artifact)
    out.to_csv("predicted_segments.csv", index=False)
    print(out[["customer_id","segment_id","segment_name"]].head(20).to_string(index=False))
    print("\nSaved predicted_segments.csv")
