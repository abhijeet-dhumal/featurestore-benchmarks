FROM locustio/locust:2.20.0

USER root

# Install Feast
RUN pip install feast[redis]==0.60.0 numpy pandas pyarrow

# Copy benchmark files
COPY locustfile_feast.py /home/locust/
COPY common/ /home/locust/common/
COPY feast_configuration.json /home/locust/

USER locust

WORKDIR /home/locust
