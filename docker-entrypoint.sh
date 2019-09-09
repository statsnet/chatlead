#!/bin/sh
set -e

# Go to directory
cd $PROJECT_PATH

# Activate virtualenv
source .venv/bin/activate
python manage.py compilemessages > /dev/null

# Change permission
chmod 775 -R $PROJECT_PATH/uploads
chown app:app -R $PROJECT_PATH/uploads

# Test
if [[ $DJANGO_SETTINGS_MODULE == 'chat_api.settings_test' ]]; then
    echo "Run testing mode"

    # Run test
    exec gosu app python manage.py test --noinput
    exit
else
    echo "Run production mode"

    # Run migration
    gosu app python manage.py migrate

    # Run project
    if [[ $WORKER == 'True' ]]; then
        exec gosu app celery -A chat_api worker -l info
    elif [[ $CRON == 'True' ]]; then
        exec gosu app celery -A chat_api worker -l info -B -s /home/app/celerybeat-schedule
    else
        # Static files
        python manage.py collectstatic --noinput
        chmod 775 -R $PROJECT_PATH/static
        chown app:app -R $PROJECT_PATH/static
        exec gosu app gunicorn chat_api.wsgi -b 0.0.0.0:8000
    fi

    exit
fi