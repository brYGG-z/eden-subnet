#!/bin/bash

# MIT License - Copyright (c) 2023 Bakobiibizo (https://github.com/bakobiibizo)

set -e

register() {
    module_path="$1"
    key_name="$1"
    host="$2"
    port="$3"
    netuid="$4"
    stake="$5"
    filename="${module_path%%.*}"

    echo "Transfer complete. Registering miner"
    comx module register "$key_name" "$key_name" --ip "$host" --port "$port" --netuid "$netuid" --stake "$stake"
    echo "Registered $key_name"

    echo "Serving"
    pm2 start "python -m eden_subnet.miner.$filename --key_name $key_name --host 0.0.0.0 --port $port" --name "$module_path"
    echo "Served"
}
NAMES=("Miner_14" "Miner_15" "Miner_16" "Miner_17" "Miner_18" "Miner_19" "Miner_20")
HOSTS=("146.190.188.174" "146.190.188.174" "146.190.188.174" "146.190.188.174" "146.190.188.174" "146.190.188.174" "146.190.188.174")
PORTS=("50187" "50186"  "50185" "50184"  "50183" "50182"  "50181")

for ((i = 0; i < ${#HOSTS[@]}; i++)); do
    PORT=${PORTS[i]}
    HOST=${HOSTS[i]}

    NETUID="10" # Replace with your actual netuid
    STAKE="82.5"  # Replace with your actual stake
    TRANSFER="83"
    FILENAME="cat"
    CLASSNAME=${NAMES[i]}
    TRANSFERFROM=brygg2
    NAME="$FILENAME.$CLASSNAME"

    if [ ! -f "$HOME/.commune/key/$NAME.json" ]; then
        comx key create "$NAME"
    fi

    comx balance transfer "$TRANSFERFROM" "$TRANSFER" "$NAME"
    echo "Transfer of $TRANSFER from $TRANSFERFROM to $NAME initiated."

    register "$NAME" "$HOST" "$PORT" "$NETUID" "$STAKE"
done