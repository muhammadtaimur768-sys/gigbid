from airflow import DAG

with DAG('daily_refresh', schedule='0 6 * * *') as dag:
    pass


import sys
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('out')
