FROM python:3.9-slim

RUN pip3 install --no-cache-dir fastapi uvicorn PyJWT grpcio grpcio-tools protobuf confluent-kafka

WORKDIR /app

COPY post.proto /app/

RUN python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. post.proto

COPY . /app

EXPOSE 50051

CMD ["python", "post_service.py"]