FROM ubuntu:latest
RUN apt-get update && \
    apt-get install -y python3.9 \
    python3-pip curl

RUN pip3 install JPype1 jupyter pandas numpy seaborn scipy matplotlib pyNetLogo SALib
RUN pip3 install numpy pandas matplotlib plyvel protobuf==3.20.0 tqdm notebook markupsafe==2.0.1

WORKDIR home/jupyter
COPY . .
EXPOSE 8888
ENTRYPOINT ["jupyter", "notebook","--allow-root","--ip=0.0.0.0","--port=8888","--no-browser"]

