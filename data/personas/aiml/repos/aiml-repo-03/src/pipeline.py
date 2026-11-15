# build: docker build -t svc . && docker run -p 8000:8000 svc
IMAGE = 'svc:latest'


from sklearn.metrics import classification_report

print(classification_report(y_true, y_pred, digits=3))


from pathlib import Path
import argparse

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path)
    args = parser.parse_args()
