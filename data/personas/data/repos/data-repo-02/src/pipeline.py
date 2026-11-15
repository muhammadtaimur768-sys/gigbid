import sys
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('out')


import pandas as pd

df = pd.read_csv('orders.csv', parse_dates=['date'])
pivot = df.pivot_table(index='region', columns='month', values='revenue', aggfunc='sum')
