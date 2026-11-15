def extract_load(source: str, table: str) -> int:
    rows = fetch(source)
    load(table, rows)
    return len(rows)


from airflow import DAG

with DAG('daily_refresh', schedule='0 6 * * *') as dag:
    pass
