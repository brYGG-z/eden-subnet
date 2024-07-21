import asyncio
import ipaddress
import time
from time import sleep
import subprocess
import json
import os
import re
import shutil
import digitalocean
from communex.compat.key import Ss58Address
from loguru import logger

# Set the environment variable
os.environ['COMX_YES_TO_ALL'] = 'true'
os.environ['COMX_OUTPUT_JSON'] = 'true'
os.environ["DO_API_TOKEN"] = 'ENTER YOUR DIGITALOCEAN API TOKEN HERE'


# Function to validate the module path
def module_filename_check(module_filename):
    while True:
        if re.match(r'^[a-zA-Z_]\w*(\.[a-zA-Z_]\w*)*$', module_filename):
            return module_filename
        else:
            print("Invalid characters in module path. Please try again.")
            module_filename = input("Enter module name: ")


def serve_modules(module_filename, index, source_module, port, NumModules, Netuid):

    for i in range(NumModules):

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

def register(module_filename, index, wan_ip, wan_ip_2, port, NumModules, Netuid, source_key, stake):

    ip = wan_ip

    for i in range(NumModules):
        if i == 10:
            ip = wan_ip_2
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
            value = subprocess.run(["comx", "module", "register", "--ip", ip, "--port", f"{next_port}", "--stake", str(stake - 0.5), module_name, module_name, "--netuid", f"{Netuid}"], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error registering miner, {e}")
        except Exception as e:
            logger.error(f"Error processing thing:\n{e}")        
        print(f"Registered {module_name} at {ip}:{next_port}")
        sleep(10)

# NGINX Droplet creation methods
def get_user_input():
    droplet_name = input("Enter a name for your droplet: ")
    target_ip = input("Enter the IP address to route traffic to: ")
    start_port = int(input("Enter the starting port number: "))
    num_ports = int(input("Enter the number of port forwards to add: "))
    return droplet_name, target_ip, start_port, num_ports

def get_ssh_password():
    while True:
        password = input("Enter the SSH password for the root user (or press Enter to skip): ")
        if not password:
            return None
        confirm = input("Confirm password: ")
        if password == confirm:
            return password
        print("Passwords do not match. Please try again.")

def create_nginx_config(public_ipv4, target_ip, start_port, num_ports):
    config = f"""
user www-data;
worker_processes auto;
pid /run/nginx.pid;
include /etc/nginx/modules-enabled/*.conf;

events {{
    worker_connections 768;
}}

http {{
"""
    
    for i in range(num_ports):
        port = start_port + i
        config += f"""
    server {{
        listen {port};
        server_name {public_ipv4};

        location / {{
            proxy_pass http://{target_ip}:{port};
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}
    }}
"""
    
    config += "}\n"
    return config

def create_user_data_script(target_ip, start_port, num_ports, ssh_password=None):
    script = f"""#!/bin/bash

# Fetch the droplet's public IPv4 address from metadata
PUBLIC_IPV4=$(curl -s http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address)

# Create a custom NGINX configuration
cat > /etc/nginx/nginx.conf <<EOL
{create_nginx_config("$PUBLIC_IPV4", target_ip, start_port, num_ports)}
EOL

# Configure UFW to open TCP ports
ufw allow {start_port}:{start_port + num_ports - 1}/tcp

# Enable UFW
ufw --force enable

# Restart NGINX to apply changes
systemctl restart nginx
"""

    if ssh_password:
        script += f"""
# Set root password
echo 'root:{ssh_password}' | chpasswd

# Enable password authentication in SSH
sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Restart SSH service
systemctl restart sshd
"""

    return script

def create_nginx_droplet(api_token, droplet_name, target_ip, start_port, num_ports, ssh_password):
    manager = digitalocean.Manager(token=api_token)
    
    droplet = digitalocean.Droplet(
        token=api_token,
        name=droplet_name,
        region="sfo3",  # San Francisco region
        image="nginx",  # NGINX image
        size_slug="s-1vcpu-1gb",
        user_data=create_user_data_script(target_ip, start_port, num_ports, ssh_password),
    )
    
    droplet.create()
    
    print(f"Creating droplet: {droplet.name}")
    actions = droplet.get_actions()
    for action in actions:
        action.load()
        print(f"Droplet status: {action.status}")
        action.wait()
    
    # Refresh the droplet information to get the IP address
    droplet.load()
    
    # Wait for the IP address to be available (with a 5-minute timeout)
    timeout = time.time() + 5 * 60  # 5 minutes from now
    while not droplet.ip_address:
        if time.time() > timeout:
            print("Timed out waiting for IP address")
            return None
        time.sleep(5)
        droplet.load()
    
    print(f"Droplet created successfully. IP: {droplet.ip_address}")
    
    return droplet

def print_ssh_config_entry(droplet_name, ip_address):
    config_entry = f"""
Host {droplet_name}
    HostName {ip_address}
    User root
    Port 22
"""
    print("\nSSH config entry for your droplet:")
    print(config_entry)
    print("You can copy this entry into your local SSH config file.")

def add_droplet_to_firewall(api_token, droplet):
    manager = digitalocean.Manager(token=api_token)
    
    while True:
        firewall_name = input("Enter the name of the firewall to add the droplet to: ")
        
        # Get all firewalls
        firewalls = manager.get_all_firewalls()
        
        # Find the firewall by name
        target_firewall = next((fw for fw in firewalls if fw.name == firewall_name), None)
        
        if target_firewall is None:
            print(f"Firewall '{firewall_name}' not found.")
            print("Available firewalls:")
            for fw in firewalls:
                print(f"- {fw.name}")
            print("Please try again.")
        else:
            # Add the droplet to the firewall
            target_firewall.add_droplets([droplet.id])
            print(f"Droplet {droplet.name} (ID: {droplet.id}) added to firewall '{firewall_name}'")
            break

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
    start_port = 0

    # Ask the user if they want to launch an NGINX droplet
    launch_nginx = input("Do you want to launch an NGINX droplet? (y/n): ")
    if launch_nginx.lower() == "y":
        api_token = os.getenv("DO_API_TOKEN")
        if not api_token:
            api_token = input("Enter your DigitalOcean API token: ")
        droplet_name = input("Enter a name for your droplet: ")
        target_ip = get_valid_ip_address("Enter the IP address to route traffic to: ")
        start_port = get_valid_numeric_input("Enter the starting port number: ")
        num_ports = get_valid_numeric_input("Enter the number of port forwards to add: ")
        ssh_password = get_ssh_password()
        droplet = create_nginx_droplet(api_token, droplet_name, target_ip, start_port, num_ports, ssh_password)
        if droplet:
            add_droplet_to_firewall(api_token, droplet)
            print_ssh_config_entry(droplet_name, droplet.ip_address)
        else:
            print("Failed to create NGINX droplet. Exiting.")
            exit(1)
    else:
        print("Skipping NGINX droplet creation.")

    # Ask the user for the module filename
    module_filename = input("Enter module name: ")

    # Ask the user for the starting module index
    index = get_valid_numeric_input("Enter starting module index (default is 0): ")

    # Ask the user for the number of modules
    NumModules = get_valid_numeric_input("Enter the number of modules: ")

    # Ask user for the module stake inclusive of the burn fee
    stake = get_valid_numeric_input("Enter stake (including burn fee): ", True)

    # Calculate the total required funding
    total_funding = NumModules * stake

    # Display the message with the required funding amount
    source_key = input(f"Enter source funding key (balance must be at least {total_funding:.2f}): ")

    # Ask the user for the WAN IP
    wan_ip = get_valid_ip_address("Enter the WAN IP: ")
    if NumModules > 10:
        # Ask the user for the second WAN IP
        wan_ip_2 = get_valid_ip_address("Enter the second WAN IP: ")
    else:
        wan_ip_2 = None

    # Ask the user for the starting port if they didn't already specify it for droplet creation
    if start_port == 0:
        start_port = get_valid_numeric_input("Enter the starting port number: ")

    source_module = source_miner
    Netuid = 10


    serve_modules(module_filename=module_filename,index=index,source_module=source_miner,port=start_port, NumModules=NumModules, Netuid=Netuid)
    register(
        module_filename=module_filename,
        index=index,
        wan_ip=wan_ip,
        wan_ip_2=wan_ip_2,
        port=start_port,
        NumModules=NumModules,
        Netuid=Netuid,
        source_key=source_key,
        stake=stake
    )


    
