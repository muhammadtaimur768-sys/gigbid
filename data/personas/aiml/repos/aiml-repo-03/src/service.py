from fastapi import FastAPI

app = FastAPI()

@app.post('/predict')
def predict(req: Request) -> Response:
    return Response(label=model(req.text))


import torch
from torch import nn

class Head(nn.Module):
    def __init__(self, d: int, n: int):
        super().__init__()
        self.proj = nn.Linear(d, n)

    def forward(self, x):
        return self.proj(x)
