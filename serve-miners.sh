#!/bin/bash

# MIT License - Copyright (c) 2024 brYGG-z (https://github.com/brYGG-z)

set -e

# This is all your miner information that will be used to serve the miners - change it to your particulars
HOST="xxx.xxx.xxx.xxx"
PORTS=("port1" "port2" "port3" "port4" "port5" "port6" "port7" "port8" "port9")
NAMES=("Miner.Miner1" "Miner.Miner2" "Miner.Miner3" "Miner.Miner4" "Miner.Miner5" "Miner.Miner6" "Miner.Miner7" "Miner.Miner8" "Miner.Miner9")

for ((i=0; i<${#NAMES[@]}; i++)); do
  filename="${NAMES[i]%%.*}"
  module_path="${NAMES[i]}"
  port="${PORTS[i]}"

  echo "Serving miner: $module_path at $HOST:$port"
  pm2 start "python -m eden_subnet.miner.$filename --key_name $module_path --host $HOST --port $port" --name "$module_path"
  echo "Miner served."
done