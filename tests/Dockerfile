FROM python:3

ENV POETRY_VERSION 1.6.1
ENV VIRTUAL_ENV /usr/venv
ENV PATH $VIRTUAL_ENV/bin:/root/.local/bin:$PATH

WORKDIR /usr/src/app

RUN python -m venv $VIRTUAL_ENV
ADD https://install.python-poetry.org /tmp/install-poetry.py
RUN python /tmp/install-poetry.py

COPY poetry.lock pyproject.toml ./
RUN poetry install --no-root

COPY . .
RUN pip install --editable . --no-deps

CMD sh -c "coverage run -m pytest && coverage report"
