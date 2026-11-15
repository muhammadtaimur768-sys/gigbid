import boto3

s3 = boto3.client('s3')
s3.upload_file('model.tar.gz', BUCKET, 'models/model.tar.gz')


from airflow import DAG
from airflow.operators.python import PythonOperator

with DAG('retrain', schedule='@daily') as dag:
    PythonOperator(task_id='train', python_callable=train)
