from pathlib import Path
import argparse

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path)
    args = parser.parse_args()


from transformers import AutoTokenizer, AutoModelForSequenceClassification

tok = AutoTokenizer.from_pretrained(CKPT)
model = AutoModelForSequenceClassification.from_pretrained(CKPT, num_labels=6)
