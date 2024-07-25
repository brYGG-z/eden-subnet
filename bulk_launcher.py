import ipaddress
import time
from time import sleep
import subprocess
import json
import os
import sys
import re
import shutil
import logging
from communex.compat.key import Ss58Address
from loguru import logger
from droplet_launcher import create_nginx_redirect

# Set the environment variable
os.environ['COMX_YES_TO_ALL'] = 'true'
os.environ['COMX_OUTPUT_JSON'] = 'true'


# Function to validate the module path
def module_filename_check(module_filename):
    while True:
        if re.match(r'^[a-zA-Z_]\w*(\.[a-zA-Z_]\w*)*$', module_filename):
            return module_filename
        else:
            print("Invalid characters in module path. Please try again.")
            module_filename = input("Enter module name: ")


def serve_modules(module_filename, index, source_module, port, num_ports, Netuid):

    for i in range(num_ports):

        # Separates by filename and classname (by the dot)
        filename = module_filename_check(module_filename)
        classname_instance = f"Miner_{index + i}"
        module_name = f"{module_filename}.{classname_instance}"
        next_port = port + i

        # Create keys for the modules if they don't exist
        key_path = os.path.expanduser(f"~/.commune/key/{module_name}.json")
        if not os.path.isfile(key_path):
            subprocess.run(["comx", "key", "create", module_name])

        # Check if the destination file does not exist
        source_directory = os.path.dirname(source_module)
        # Define the new file path
        new_file_path = os.path.join(source_directory, filename + ".py")
        if not os.path.isfile(new_file_path):
            # Copy the source module to the new file path
            shutil.copy(source_module, new_file_path)            

        print("Serving Miner")
        command = f'pm2 start "python -m eden_subnet.miner.{filename} --key_name {module_name} --host 0.0.0.0 --port {next_port}" --name "{module_name}"'
        os.system(command)
        print("Miner served.")


def get_ss58_address(name):
    # Construct the path to the JSON file
    file_path = os.path.expanduser(f"~/.commune/key/{name}.json")

    try:
        # Open and read the JSON file
        with open(file_path, 'r') as file:
            data = json.load(file)

        # Extract the 'data' field and parse it as JSON
        data_json = json.loads(data['data'])

        # Return the 'ss58_address' field
        return data_json['ss58_address']

    except FileNotFoundError:
        print(f"No file found for {name}")
        return None
    except KeyError as e:
        print(f"Key error: {e} - Check JSON structure")
        return None
    except json.JSONDecodeError:
        print("Error decoding JSON")
        return None
    except Exception as e: 
        logger.error(f"Error procesing thing:\n{e}")
        return None

def register(module_filename, index, ipv4, reserved_ip, port, num_ports, Netuid, source_key, stake):

    ip = ipv4

    for i in range(num_ports):
        if i == 10:
            ip = reserved_ip
        key = source_key
        module_name = f"{module_filename}.Miner_{index + i}"
        next_port = port + i
        ss58 = Ss58Address(module_name)
        print("Port: ", next_port)
        print("Transfer Com to new miner key")
        try:
            value = subprocess.run(["comx", "balance", "transfer", key, str(stake), ss58], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(value.stdout)
        except Exception as e:
            logger.error(f"Error processing thing:\n{e}")
        sleep(10)

        print("Register new miner key")
        try:
            value = subprocess.run(["comx", "module", "register", "--ip", ip, "--port", f"{next_port}", module_name, module_name, "--netuid", f"{Netuid}"], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error registering miner, {e}")
        except Exception as e:
            logger.error(f"Error processing thing:\n{e}")        
        print(f"Registered {module_name} at {ip}:{next_port}")
        sleep(5)
        print("Stake miner")
        try:
            value = subprocess.run(["comx", "balance", "stake", module_name, str(stake - 10.5), module_name], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error staking miner, {e}")
        except Exception as e:
            logger.error(f"Error processing thing:\n{e}")        
        print(f"Staked {str(stake - 10.5)} to {module_name}")
        sleep(5)


def get_valid_numeric_input(message, is_float=False):
    default = 0.0 if is_float else 0
    while True:
        input_value = input(message)
        if input_value == "":
            return default
        try:
            if is_float:
                return float(input_value)
            else:
                return int(input_value)
        except ValueError:
            print("Invalid entry. Please enter a valid number.")


def get_valid_ip_address(message):
    while True:
        ip_address = input(message)
        try:
            ipaddress.ip_address(ip_address)
            return ip_address
        except ValueError:
            print("Invalid IP address. Please enter a valid IP address.")



if __name__ == "__main__":
    source_miner = "eden_subnet/miner/eden.py"
    source_validator = "eden_subnet/validator/validator.py"
    ipv4 = None
    reserved_ip = None
    starting_port = None
    num_ports = None

    # Ask the user if they want to launch an NGINX droplet
    launch_nginx = input("Do you want to launch an NGINX droplet? (y/n): ")
    if launch_nginx.lower() == "y":
        ipv4, reserved_ip, starting_port, num_ports = create_nginx_redirect()
    else:
        print("Skipping NGINX droplet creation.")

    # Ask the user for the module filename
    module_filename = input("Enter module name: ")

    # Ask the user for the starting module index
    index = get_valid_numeric_input("Enter starting module index (default is 0): ")

    # Ask the user for the number of modules
    if num_ports == None:
        num_ports = get_valid_numeric_input("Enter the number of modules to create: ")

    # Ask user for the module stake inclusive of the burn fee
    stake = get_valid_numeric_input("Enter stake (including burn fee): ", True)

    # Calculate the total required funding
    total_funding = num_ports * stake

    # Display the message with the required funding amount
    source_key = input(f"Enter source funding key (balance must be at least {total_funding:.2f}): ")

    # Ask the user for the WAN IP
    if ipv4 is None:
        ipv4 = get_valid_ip_address("Enter the WAN IP: ")

    # Ask the user for the second WAN IP if number of modules is greater than 10
    if num_ports > 10:
        # Ask the user for the second WAN IP
        if reserved_ip is None:
            reserved_ip = get_valid_ip_address("Enter the second WAN IP: ")

    # Ask the user for the starting port if they didn't already specify it for droplet creation
    if starting_port == None:
        starting_port = get_valid_numeric_input("Enter the starting port number: ")

    source_module = source_miner
    Netuid = 10


    serve_modules(module_filename=module_filename,index=index,source_module=source_miner,port=starting_port, num_ports=num_ports, Netuid=Netuid)
    register(
        module_filename=module_filename,
        index=index,
        ipv4=ipv4,
        reserved_ip=reserved_ip,
        port=starting_port,
        num_ports=num_ports,
        Netuid=Netuid,
        source_key=source_key,
        stake=stake
    )


    
