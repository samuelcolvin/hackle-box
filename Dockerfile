FROM python:3.5.2-alpine
MAINTAINER Samuel Colvin <s@muelcolvin.com>

RUN apk update && apk upgrade && apk add --no-cache git openssh

ADD requirements.txt /
WORKDIR /
RUN pip install -r requirements.txt

ADD app /app
ADD main.py /

ENV GITHUB_USER samuelcolvin
ENV GITHUB_REPO gaugemore.com
ENV SRC_DIR /src

EXPOSE 8000
ENTRYPOINT ["python", "main.py"]
