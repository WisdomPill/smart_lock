#!/bin/bash

#not really the best because it was hitting limits quite fast

mkdir results

docker-compose up -d

locust --host http://localhost:8000 -u 400 -r 50 -t 60 \
  --autostart --autoquit 0 --print-stats --reset-stats --csv results/redis-entry-redis-lock.csv RedisEntryRedisLockUser

docker-compose down

printf "\n\n\n\n\n"

docker-compose up -d

locust --host http://localhost:8000 -u 400 -r 50 -t 60 \
  --autostart --autoquit 0 --print-stats --reset-stats --csv results/django-entry-django-lock.csv DjangoEntryDjangoLockUser

docker-compose down

printf "\n\n\n\n\n"

docker-compose up -d

locust --host http://localhost:8000 -u 400 -r 50 -t 60 \
  --autostart --autoquit 0 --print-stats --reset-stats --csv results/redis-entry-django-lock.csv RedisEntryDjangoLockUser

docker-compose down

printf "\n\n\n\n\n"

docker-compose up -d

locust --host http://localhost:8000 -u 400 -r 50 -t 60 \
  --autostart --autoquit 0 --print-stats --reset-stats --csv results/django-entry-django-lock.csv DjangoEntryDjangoLockUser

docker-compose down
