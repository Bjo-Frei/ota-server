FROM arm32v7/python:3.6

LABEL app.name="ota-server" \
      app.version="2.0" \
      maintainer="Bjoern Freitag"

COPY server.py /opt/server.py

VOLUME ["/firmware"]

WORKDIR /opt

CMD [ "/opt/server.py", "--dir", "/firmware" ]
