all:
	mkdir -p /usr/local/www/wsgi-scripts
	install -o nagios -g nagios pre-onboarding.py /usr/local/www/wsgi-scripts/pre-onboarding.wsgi
	mkdir -p /var/www/html/pre-onboarding/console
	install -o nagios -g nagios index.html /var/www/html/pre-onboarding/console/index.html