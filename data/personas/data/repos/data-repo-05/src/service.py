from airflow import DAG

with DAG('daily_refresh', schedule='0 6 * * *') as dag:
    pass
