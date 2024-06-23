#!/bin/bash

# MIT License - Copyright (c) 2024 brYGG-z (https://github.com/brYGG-z)

set -e

# This is all your miner information that will be used to serve the miners - change it to your particulars
HOST="0.0.0.0"
PORTS=("50188" "50189" "50190" "50191" "50192" "50193" "50194" "50195" "50196" "50197" "50198" "50199" "50200" "50187" "50186" "50185" "50184" "50183" "50182" "501981")
NAMES=("cat.Miner_1" "cat.Miner_2" "cat.Miner_3" "cat.Miner_4" "cat.Miner_5" "cat.Miner_6" "cat.Miner_7" "cat.Miner_8" "cat.Miner_9" "cat.Miner_10" "cat.Miner_11" "cat.Miner_12" "cat.Miner_13" "cat.Miner_14" "cat.Miner_15" "cat.Miner_16" "cat.Miner_17" "cat.Miner_18" "cat.Miner_19" "cat.Miner_20")

for ((i=0; i<${#NAMES[@]}; i++)); do
  filename="${NAMES[i]%%.*}"
  module_path="${NAMES[i]}"
  port="${PORTS[i]}"

  echo "Serving miner: $module_path at $HOST:$port"
  pm2 start "python -m eden_subnet.miner.$filename --key_name $module_path --host $HOST --port $port" --name "$module_path"
  echo "Miner served."
done