# Server B - SMS Relay

This Django project provides an SMS relay service with a pluggable provider interface and RabbitMQ consumer.

## Quickstart

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
npm install
npm run build  # build Tailwind CSS
python manage.py runserver
python manage.py consume_sms  # in another terminal
```

Run tests:

```bash
python manage.py test
```

Docker Compose (from repository root):

```bash
docker-compose up --build server_b_web server_b_consumer
```
