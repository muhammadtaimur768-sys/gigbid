import torch
from torch import nn

class Head(nn.Module):
    def __init__(self, d: int, n: int):
        super().__init__()
        self.proj = nn.Linear(d, n)

    def forward(self, x):
        return self.proj(x)


from sklearn.metrics import classification_report

print(classification_report(y_true, y_pred, digits=3))
