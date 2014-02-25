# Install

You first need to create a virtual environment with python3:

    $ mkvirtualenv agora-election -e $(which python3)

Then install the dependencies:

    $ pip install -r requirements.txt

Then configure the settings, take a look at agora_election/settings.py and change anything in a new file agora_election/custom_settings.py. After that, you can create the database:

    $ cd agora_election
    $ ./app.py --createdb

And launch the test/development server:

    $ ./app.py

You'd also need to launch in another terminal celery:

    $  celery -A app worker --loglevel=info

Please read flask and celery documentation for more details on how to do a proper production deployment.