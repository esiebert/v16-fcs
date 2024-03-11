FROM python:3.11.3-slim

ENV PYTHONPATH=/usr/src/app/
WORKDIR /usr/src/app/

RUN apt-get update
RUN apt-get install -y --no-install-recommends make

COPY poetry.lock ./poetry.lock
COPY pyproject.toml ./pyproject.toml

RUN pip install poetry
RUN poetry install --only main

COPY fake_charging_station ./fake_charging_station

EXPOSE 8081

CMD ["poetry", "run", "uvicorn", "fake_charging_station.app:app", "--host", "0.0.0.0", "--port", "8081"]