#!/bin/bash

PORT_MIN=$1
PORT_MAX=$2

LOG_FILEPATH="/tmp/redis-$(uuidgen).log"


if [[ -z $PORT_MIN || -z $PORT_MAX ]]; then
  echo "error: missing port arguments"; exit 1
fi

touch $LOG_FILEPATH


for port in $(seq $PORT_MIN $PORT_MAX)
do
  echo "running: redis-cli -p $port monitor"
  redis-cli -p $port monitor >> $LOG_FILEPATH &
done

sleep 1

tail -f $LOG_FILEPATH | grep -v "PING" | grep -v '"INFO"$' | grep -v "__sentinel__:hello"
