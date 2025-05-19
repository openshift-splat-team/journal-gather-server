FROM registry.access.redhat.com/ubi9/python-312-minimal:9.6-1747319120

RUN pip install flask

COPY serve.py .

CMD python serve.py