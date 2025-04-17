FROM python:3.9-slim

#RUN apt-get update && apt-get install -q -y git

COPY ./dist/fastapi_aws-*.whl .

COPY ./requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
RUN pip install --no-cache-dir *.whl

WORKDIR /app

ENTRYPOINT ["python", "-m", "fastapi_aws", "api_stub:app"]

#CMD ["--out", "/out/openapi.json"]
