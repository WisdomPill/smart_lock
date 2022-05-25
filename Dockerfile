FROM python:3.10-alpine

# create user `smart_lock` and add it to group `smart_lock`
RUN addgroup -S smart_lock && adduser -S -G smart_lock smart_lock

ARG dev

ENV IS_DEV_ENV=${dev:+dev-requirements.txt}

ENV REQUIREMENTS=${IS_DEV_ENV:-requirements.txt}

RUN pip install -U pip setuptools pipenv

COPY Pipfile* ./

# install python requirements
RUN apk add --no-cache --virtual .build-deps \
    ca-certificates postgresql-dev musl-dev  \
    libffi-dev openssl-dev cargo jpeg-dev \
    freetype-dev zlib-dev build-base \
    && pipenv lock -r > requirements.txt \
    && pipenv lock -r --dev > dev-requirements.txt \
    && pip uninstall --yes pipenv \
    && pip install -r ${REQUIREMENTS} \
    && find /usr/local \
        \( -type d -a -name test -o -name tests \) \
        -o \( -type f -a -name '*.pyc' -o -name '*.pyo' \) \
        -exec rm -rf '{}' + \
    && runDeps="$( \
        scanelf --needed --nobanner --recursive /usr/local \
                | awk '{ gsub(/,/, "\nso:", $2); print "so:" $2 }' \
                | sort -u \
                | xargs -r apk info --installed \
                | sort -u \
    )" \
    && apk add --virtual .rundeps $runDeps \
    && apk del .build-deps

# set envirnoment variables
ENV SRC=smart_lock
ENV USER_HOME=/home/smart_lock
ENV CODE_DIR=$USER_HOME/$SRC

WORKDIR $CODE_DIR

# copy all the code
COPY . $CODE_DIR

RUN chown -R smart_lock:smart_lock $CODE_DIR

USER smart_lock

ENTRYPOINT ["python3", "manage.py"]
