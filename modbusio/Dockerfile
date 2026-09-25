ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache bash

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

COPY app /app
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
