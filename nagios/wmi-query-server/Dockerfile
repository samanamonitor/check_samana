FROM ubuntu:bionic AS pywmi
RUN apt update && apt install -y python3 libpython3.6 libjansson4 iputils-ping apache2 libapache2-mod-wsgi-py3
COPY pywmi.so /usr/lib/python3/dist-packages
COPY wmi-query-server.conf /etc/apache2/conf-available
RUN mkdir -p /usr/local/nagios/share/wsgi/
COPY wmi-query-server.py /usr/local/nagios/share/wsgi/
RUN a2enconf wmi-query-server
RUN mkdir -p /usr/lib/python3/dist-packages/samana
COPY base.py etcd.py nagios.py /usr/lib/python3/dist-packages/samana/
COPY start.sh /
ENTRYPOINT /start.sh
