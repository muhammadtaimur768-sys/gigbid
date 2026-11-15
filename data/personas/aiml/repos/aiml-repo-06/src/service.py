from sklearn.model_selection import cross_val_score
from sklearn.ensemble import GradientBoostingClassifier

scores = cross_val_score(GradientBoostingClassifier(), X, y, cv=5)


from pathlib import Path
import argparse

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path)
    args = parser.parse_args()
