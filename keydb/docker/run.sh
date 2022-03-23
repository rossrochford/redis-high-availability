#!/bin/bash


if [[ $INSTANCE_TYPE == "master" ]]; then
  keydb-server /etc/keydb/keydb.conf
elif [[ $INSTANCE_TYPE == "replica" ]]; then
  keydb-server /etc/keydb/keydb.conf --replica-announce-ip "$SELF_IP" --replicaof "$MASTER_IP" 6379
elif [[ $INSTANCE_TYPE == "sentinel" ]]; then
  sed -i "s|__SELF_IP__|$SELF_IP|g" /etc/keydb/sentinel.conf
  sed -i "s|__MASTER_IP__|$MASTER_IP|g" /etc/keydb/sentinel.conf
  keydb-sentinel /etc/keydb/sentinel.conf
fi
