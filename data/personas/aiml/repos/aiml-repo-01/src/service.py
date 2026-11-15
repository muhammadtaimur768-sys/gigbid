# build: docker build -t svc . && docker run -p 8000:8000 svc
IMAGE = 'svc:latest'


from fastapi import FastAPI

app = FastAPI()

@app.post('/predict')
def predict(req: Request) -> Response:
    return Response(label=model(req.text))
