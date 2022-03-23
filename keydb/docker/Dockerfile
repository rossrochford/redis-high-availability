FROM eqalpha/keydb:x86_64_v6.2.0

#RUN apt update -y
#RUN apt install vim -y

COPY conf/keydb.conf /etc/keydb/keydb.conf
COPY conf/sentinel.conf /etc/keydb/sentinel.conf
COPY run.sh /root/run.sh

RUN chmod +x /root/run.sh

CMD ["/root/run.sh"]
