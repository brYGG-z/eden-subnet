#!/bin/bash

# MIT License - Copyright (c) 2023 Bakobiibizo (https://github.com/bakobiibizo)

set -e

# Set the environment variable
export COMX_YES_TO_ALL=true

source_miner="eden_subnet/miner/eden.py"
source_validator="eden_subnet/validator/eden.py"


# Configures the module launch
configure_launch() {
    # Enter the path of the module
    echo "The module name is the module path as well."
    echo "It should be in the format of \"filename.ClassName\" (eg. eden.Miner_1)"
    # shellcheck disable=SC2162
    read -p "Module Path: " module_path

    # Check if the module path is valid
    if [ "$module_path" = "" ]; then
        echo "Error, must provide a valid module path."
        # shellcheck disable=SC2162
        read -p "Module Path: " module_path
    elif [ -z "$module_path" ]; then
        echo "Error, must provide a valid module path."
        exit 1
    fi

    # Extract the filename and classname
    filename="${module_path%%.*}"
    classname="${module_path#*.}"

    echo "Checking file path"
    # Create the miner module if it doesn't exist
    if [ "$is_miner" = "true" ]; then
        if [ ! -f "eden_subnet/miner/$filename.py" ]; then
            # Copy the source miner file to the destination
            destination_file="eden_subnet/miner/$filename.py"
            cp "$source_miner" "$destination_file"
            # Replace the class name in the destination file
            sed -i "s/Miner_1/$classname/g" "$destination_file"
            echo "Miner module created at eden_subnet/miner/$filename.py"
        fi
    fi

    # Create the validator module if it doesn't exist
    if [ "$is_validator" = "true" ]; then
        if [ ! -f "eden_subnet/validator/$filename.py" ]; then
            # Copy the source validator file to the destination
            destination_file="eden_subnet/validator/$filename.py"
            cp "$source_validator" "$destination_file"
            # Replace the class name in the destination file
            sed -i "s/Validator_1/$classname/g" "$destination_file"
            echo "Validator module created at eden_subnet/validator/$filename.py"
        fi
    fi
    echo "Module path exists"
    echo ""

    #    # Enter the name of the key that will be used to stake the validator
    #    echo "The name of the key that will be used to stake the validator. Defaults to Module Path ($module_path) if not provided."
    #    # shellcheck disable=SC2162
    #    read -p "Module key name: " key_name
    #    if [ "$key_name" = "" ]; then
    key_name=$module_path
    #    fi
    #    echo "Module key name: $key_name"
    #    echo ""

    if [ ! -f "$HOME/.commune/key/$key_name.json" ]; then
        create_key
    fi
    echo ""

    # Select if a balance needs to be transfered to the key
    echo "Transfer staking balance to the module key."
    echo "You can skip this step if you have enough balance on your key."
    echo "The sending key must be in the ~/.commune/key folder with enough com to transfer."
    # shellcheck disable=SC2162
    read -p "Transfer balance (y/n): " transfer_balance
    if [ "$transfer_balance" = "y" ]; then
        transfer_balance
    fi
    echo ""

    # Enter the IP and port of the module
    # shellcheck disable=SC2162
    read -p "Module IP address (default 0.0.0.0): " host
    if [ "$host" = "" ]; then
        host="0.0.0.0"
    fi
    echo "Module IP address: $host"
    echo ""

    # Enter the port of the module
    # shellcheck disable=SC2162
    read -p "Module port(default 10001) int: " port
    if [ "$port" = "" ]; then
        port=10001
    fi
    echo "Module port: $port"
    echo ""

    # Enter the netuid of the module
    # shellcheck disable=SC2162
    read -p "Deploying to subnet (default 10): int: " netuid
    if [ -z "$netuid" ]; then
        netuid=10
    fi
    echo "Module netuid: $netuid"
    echo ""

    # Check if the module needs to be staked
    if [ "$needs_stake" = "true" ]; then
        echo "Set the stake. This is the amount of tokens that will be staked by the module."
        echo "Validators require a balance of 5200, not including fees, to vote."
        echo "Miners require a balance of 256, not including fees, to mine."
        echo "There will be a burn fee that starts at 10 com and scales based on demand"
        echo "will be burned as a fee to stake. Make sure you have enough to cover the cost."
        # shellcheck disable=SC2162
        read -p "Set stake: " stake
        echo "Setting stake: $stake"
        echo ""
    fi

    # Enter the delegation fee
    if [ "$is_update" = "true" ]; then
        echo "Set the delegation fee. This the percentage of the emission that are collected as a fee to delegate the staked votes to the module."
        # shellcheck disable=SC2162
        read -p "Delegation fee (default 20) int: " delegation_fee
        echo ""
    fi

    # Check it is above minimum
    if [ "$delegation_fee" -lt 5 ] || [ "$delegation_fee" = "" ]; then
        echo "Minimum delegation fee is 5%. Setting to 5%"
        delegation_fee=5
        echo "Module delegation fee: $delegation_fee"
        echo ""
    fi

    # Enter the metadata
    if [ "$is_update" = "true" ]; then
        echo "Set the metadata. This is an optional field."
        echo "It is a JSON object that is passed to the module in the format:"
        echo "{\"key\": \"value\"}."
        # shellcheck disable=SC2162

        read -p "Add metadata (y/n): " choose_metadata
        if [ "$choose_metadata" = "y" ]; then
            # shellcheck disable=SC2162
            read -p "Enter metadata object: " metadata
            echo "Module metadata: $metadata"
        fi
        echo ""
    fi

    # Confirm settings
    echo "Confirm module settings:"
    echo "Module path:        $module_path"
    echo "Module IP address:  $host"
    echo "Module port:        $port"
    echo "Module netuid:      $netuid"
    echo "Module key name:    $key_name"
    if [ "$needs_stake" = "true" ]; then
        echo "Module stake:       $stake"
    fi
    if [ "$is_update" = "true" ]; then
        echo "Delegation fee:     $delegation_fee"
        echo "Metadata:           $metadata"
    fi
    # shellcheck disable=SC2162
    read -p "Confirm settings (y/n): " confirm
    if [ "$confirm" = "y" ]; then
        echo "Deploying..."
        echo ""
    else
        echo "Aborting..."
        exit 1
    fi

    # Export the variables for use in ecosystem.config.js. This allows us to use pm2 in the bash script.
    export MODULE_PATH="$module_path"
    export MODULE_IP="$host"
    export MODULE_PORT="$port"
    export MODULE_NETUID="$netuid"
    export MODULE_KEYNAME="$key_name"
    export MODULE_STAKE="$stake"
    export MODULE_DELEGATION_FEE="$delegation_fee"
    export MODULE_METADATA="$metadata"
}

# Function to create a key
create_key() {
    echo "Creating key"
    echo "This creates a json key in ~/.commune/key with the given name."
    echo "Once you create the key you will want to save the mnemonic somewhere safe."
    echo "The mnemonic is the only way to recover your key if it lost then the key is unrecoverable."
    echo "Note that commune does not encrypt the key file so do not fund a key on an unsafe machine."

    if [ -z "$key_name" ]; then
        # shellcheck disable=SC2162
        read -p "Key name: " key_name
    fi
    comx key create "$key_name"
    echo "This is your key. Save the mnemonic somewhere safe."
    cat ~/.commune/key/"$key_name".json
    echo "$key_name created and saved at ~/.commune/key/$key_name.json"
}

# Function to perform a balance transfer
transfer_balance() {
    echo "Initiating Balance Transfer"
    echo "There is a 2.5 com fee on the balance of the transfer."
    echo "Example: 300 com transfered will arrive as 297.5 com"
    # shellcheck disable=SC2162
    read -p "From Key (sender): " key_from
    # shellcheck disable=SC2162
    read -p "Amount to Transfer: " amount
    if [ -z "$key_name" ]; then
        # shellcheck disable=SC2162
        read -p "To Key (recipient): " key_to
    else
        key_to="$key_name"
    fi
    comx balance transfer "$key_from" "$amount" "$key_to"
    echo "Transfer of $amount from $key_from to $key_to initiated."
}

# Function to unstake balance from a module
unstake_and_transfer_balance() {
    local key_from="${1:-}"
    local key_to="${2:-}"
    local key_to_transfer="${3:-}"
    local subnet="${4:-}"
    local amount="${5:-}"

    if [ -z "$key_from" ] || [ -z "$key_to" ] || [ -z "$key_to_transfer" ] || [ -z "$subnet" ] || [ -z "$amount" ]; then
        echo "Initiating Balance Unstake"
        # shellcheck disable=SC2162
        read -p "Unstake from: " key_from
        # shellcheck disable=SC2162
        read -p "Unstake to: " key_to
        # shellcheck disable=SC2162
        read -p "Transfer to: " key_to_transfer
        # shellcheck disable=SC2162
        read -p "Amount to unstake: " amount
    fi

    amount_minus_half=$(echo "$amount - 0.5" | awk '{print $1 - 0.5}')
    comx balance unstake "$key_from" "$amount" "$key_to"
    echo "$amount COM unstaked from $key_from to $key_to"

    echo "Initiating Balance Transfer"
    comx balance transfer "$key_to" "$amount_minus_half" "$key_to_transfer"
    echo "Transfer of $amount_minus_half from $key_to to $key_to_transfer initiated."
}

# Function to unstake and transfer balance of all modules
unstake_and_transfer_balance_all() {
  echo "Unstaking and transferring balance of all modules..."

  # Get the module names of all modules in the .commune/key directory
  modulenames=$(find $HOME/.commune/key -type f -name "*_*" -exec basename {} \; | sed 's/\.[^.]*$//' | tr '\n' ' ')

  # Store the module names in an array
  IFS=' ' read -r -a modulenames_array <<< "$modulenames"

  unstake_and_transfer_balance_multiple "${modulenames_array[@]}"
}

# Function to unstake and transfer balance of all modules
unstake_and_transfer_balance_name() {

  declare -a module_names=()

  echo "Enter module names ('.' to stop entering module names):"
  while true; do
      read -p "Module name: " module_name
      if [[ $module_name == "." ]]; then
          break
      fi
      module_names+=("$module_name")
  done

  # Get the module names of all modules in the .commune/key directory that match the provided module names
  modulenames=$(find $HOME/.commune/key -type f -name "*_*" -print0 | 
    xargs -0 basename -a | 
    sed 's/\.[^.]*$//' | 
    grep -E "$(IFS="|"; echo "${module_names[*]}")" | 
    tr '\n' ' ')  # Store the module names in an array
  IFS=' ' read -r -a modulenames_array <<< "$modulenames"

  unstake_and_transfer_balance_multiple "${modulenames_array[@]}"
}

# Function to unstake and transfer balance of multiple modules
unstake_and_transfer_balance_multiple() {
    declare -a module_names=()

    # Check if any module names are passed as arguments
    if [[ $# -gt 0 ]]; then
        module_names=("$@")
    else
        echo "Enter module names ('.' to stop entering module names):"
        while true; do
            read -p "Module name: " module_name
            if [[ $module_name == "." ]]; then
                break
            fi
            module_names+=("$module_name")
        done
    fi

    # Ask the user for the amount
    # shellcheck disable=SC2162
    read -p "Amount to unstake from each miner: " amount

    # Ask the user for the key to transfer the balance to
    # shellcheck disable=SC2162
    read -p "Key to transfer balance to: " key_to_transfer

    # Now the module_names array contains the names of the modules entered by the user
    echo "Module names entered: ${module_names[@]}"

    # Now the amounts array contains the amounts entered by the user
    echo "Amount to unstake and transfer: $amount"

    # You can now use the module_names and amounts arrays to perform the unstake and transfer balance operations for each module
    for module_name in "${module_names[@]}"; do
        echo "Processing module: $module_name"
        unstake_and_transfer_balance "$module_name" "$module_name" "$key_to_transfer" "$subnet" "$amount"
    done

    # Print the total amount of balance transferred - amount * number of modules
    echo "Successfully transferred: $(echo "$amount * ${#module_names[@]}" | bc -l) to $key_to_transfer"
}

# Function to transfer and stake balance of multiple modules from one key
transfer_and_stake_multiple() {
    declare -a module_names=()

    # Ask the user for the amount
    # shellcheck disable=SC2162
    read -p "Amount to stake to each miner: " amount

    echo "Enter module names ('.' to stop entering module names):"
    while true; do
        read -p "Module name: " module_name
        if [[ $module_name == "." ]]; then
            break
        fi
        module_names+=("$module_name")
    done


    # Ask the user for the key to transfer the balance to
    # shellcheck disable=SC2162
    read -p "Key to transfer balance from: " key_from


    # transfer balance and stake to each miner
    for i in "${!module_names[@]}"; do
        key_to="${module_names[i]}"
    echo "Initiating Balance Transfer"
    comx balance transfer "$key_from" "$amount" "$key_to"
    echo "Transfer of $amount from $key_from to $key_to completed."
    mount_minus_half=$(echo "$amount - 0.5" | awk '{print $1 - 0.5}')
    comx balance stake "$key_to" "$mount_minus_half" "$key_to"
    echo "$amount_minus_half COM staked from $key_to to $key_to"
        
    done
}

# Function to serve a miner
serve_miner() {
    echo "Serving Miner"
    pm2 start "python -m eden_subnet.miner.$filename --key_name $key_name --host 0.0.0.0 --port $port" --name "$module_path"
    echo "Miner served."
}

# Function to register a miner
register_miner() {
    echo "Registering Miner"
    comx module register "$module_path" "$key_name" --netuid "$netuid" --stake "$stake" --ip "$host" --port "$port"
    echo "Miner registered."
}

# Function to deploy a miner
deploy_miner() {
    echo "Registering Miner"
    register_miner
    echo "Serving Miner."
    serve_miner
    echo "Miner deployed."
}

# Function to serve a validator
serve_validator() {
    echo "Serving Validator"
    pm2 start "python -m eden_subnet.validator.$filename --key_name $key_name --host $host --port $port" --name "$module_path"
    echo "Validator served."
}

# Function to register a validator
register_validator() {
    echo "Registering Validator"
    comx module register "$module_path" "$key_name" --ip "$host" --port "$port" --netuid "$netuid" --stake "$stake"
    echo "Validator registered."
}

# Function to deploy a validator
deploy_validator() {
    echo "Serving Validator"
    serve_validator
    echo "Registering Validator"
    register_validator
    echo "Validator deployed."
}

# Function to update a module
update_module() {
    echo "Updating Module"
    # This will update the metadata, netuid, and/or delegation fee.
    if [ -z "$netuid" ] && [ -z "$delegation_fee" ] && [ -z "$metadata" ]; then
        comx module update --name "$module_path" --ip "$host" --port "$port" "$key_name"
    elif [ -z "$netuid" ]; then
        comx module update --name "$module_path" --ip "$host" --port "$port" --metadata "$metadata" --delegation-fee "$delegation_fee" "$key_name"
    elif [ -z "$metadata" ]; then
        comx module update --name "$module_path" --ip "$host" --port "$port" --netuid "$netuid" --delegation-fee "$delegation_fee" "$key_name"
    elif [ -z "$delegation_fee" ]; then
        comx module update --name "$module_path" --ip "$host" --port "$port" --netuid "$netuid" --metadata "$metadata" "$key_name"
    elif [ -z "$metadata" ] && [ -z "$netuid" ]; then
        comx module update --name "$module_path" --ip "$host" --port "$port" --delegation-fee "$delegation_fee" "$key_name"
    elif [ -z "$netuid" ] && [ -z "$delegation_fee" ]; then
        comx module update --name "$module_path" --ip "$host" --port "$port" --metadata "$metadata" "$key_name"
    else
        comx module update --name "$module_path" --ip "$host" --port "$port" --netuid "$netuid" --metadata "$metadata" --delegation-fee "$delegation_fee" "$key_name"
    fi
    echo "Module updated."
}

if [ "$1" = "--setup" ]; then
    create_setup
fi

echo "Choose your deployment:"
echo "1. Deploy Validator - serve and launch"
echo "2. Deploy Miner - serve and launch"
echo "3. Deploy Both - serve and launch validator and miner"
echo "4. Register Validator"
echo "5. Register Miner"
echo "6. Serve Validator"
echo "7. Serve Miner"
echo "8. Update Module - either validator or miner"
echo "9. Transfer Balance"
echo "10. Unstake and Transfer Balance - 1 miner"
echo "11. Unstake and Transfer Balance - specific miners"
echo "12. Unstake and Transfer Balance - ALL miners"
echo "13. Unstake and Transfer Balance - ALL miners by name"
echo "14. Transfer and Stake - multiple miners"
echo "15. Create Key"
# shellcheck disable=SC2162
read -p "Choose an action " choice
echo ""

case "$choice" in
1)
    echo "Validator Configuration"
    is_validator=true
    needs_stake=true
    is_update=true
    configure_launch
    deploy_validator
    ;;
2)
    echo "Miner Configuration"
    is_miner=true
    needs_stake=true
    is_update=true
    configure_launch
    deploy_miner
    ;;
3)
    echo "Validator Configuration"
    is_validator=true
    needs_stake=true
    is_update=true
    configure_launch
    deploy_validator
    echo "Miner Configuration"
    is_validator=false
    is_miner=true
    needs_stake=true
    is_update=true
    configure_launch
    deploy_miner
    ;;
4)
    echo "Validator Configuration"
    is_validator=true
    needs_stake=true
    is_update=true
    configure_launch
    register_validator
    ;;
5)
    echo "Miner Configuration"
    is_miner=true
    needs_stake=true
    is_update=true
    configure_launch
    register_miner
    ;;
6)
    echo "Validator Configuration"
    is_validator=true
    configure_launch
    serve_validator
    ;;
7)
    echo "Miner Configuration"
    is_miner=true
    configure_launch
    serve_miner
    ;;
8)
    echo "Module Configuration"
    is_update=true
    configure_launch
    update_module
    ;;
9)
    transfer_balance
    ;;
10)
    unstake_and_transfer_balance
    ;;
11)
    unstake_and_transfer_balance_multiple
    ;;
12)
    unstake_and_transfer_balance_all
    ;;
13)
    unstake_and_transfer_balance_name
    ;;
14)
    transfer_and_stake_multiple
    ;;
15)
    create_key
    ;;
*)
    echo "Invalid choice"
    exit 1
    ;;
esac

echo "Action complete."
