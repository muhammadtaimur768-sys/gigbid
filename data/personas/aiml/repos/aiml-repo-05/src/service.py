import mlflow

with mlflow.start_run():
    mlflow.log_params(cfg)
    mlflow.log_metric('f1', f1)


# build: docker build -t svc . && docker run -p 8000:8000 svc
IMAGE = 'svc:latest'
