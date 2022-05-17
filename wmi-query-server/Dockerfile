FROM ubuntu:bionic AS pywmi
RUN apt update && apt install -y python3 libpython3.6 libjansson4 wget iputils-ping apache2 libapache2-mod-wsgi-py3
RUN wget -qO /tmp/pywmi.so.gz https://s3.us-west-2.amazonaws.com/monitor.samanagroup.co/pywmi.so.gz && gunzip /tmp/pywmi.so.gz
RUN mv /tmp/pywmi.so /usr/lib/python3/dist-packages
COPY wmi-query-server.conf /etc/apache2/conf-available
RUN mkdir -p /usr/local/nagios/share/wsgi/
COPY wmi-query-server.py /usr/local/nagios/share/wsgi/
RUN a2enconf wmi-query-server
RUN mkdir -p /usr/lib/python3/dist-packages/samana
COPY ../nagios/lib/*.py /usr/lib/python3/dist-packages/samana