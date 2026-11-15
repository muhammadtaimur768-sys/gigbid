SYSTEM = open('prompts/extract.md').read()
messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': doc}]


from fastapi import FastAPI

app = FastAPI()

@app.post('/predict')
def predict(req: Request) -> Response:
    return Response(label=model(req.text))


from pathlib import Path
import argparse

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path)
    args = parser.parse_args()
