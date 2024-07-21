import digitalocean
import os
import time

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

if __name__ == "__main__":
    api_token = os.getenv("DO_API_TOKEN")
    if not api_token:
        api_token = input("Enter your DigitalOcean API token: ")
    
    droplet_name, target_ip, start_port, num_ports = get_user_input()
    ssh_password = get_ssh_password()
    
    droplet = create_nginx_droplet(api_token, droplet_name, target_ip, start_port, num_ports, ssh_password)
    
    if droplet is None:
        print("Failed to create droplet. Exiting.")
        exit(1)
    
    # Print SSH config entry
    print_ssh_config_entry(droplet_name, droplet.ip_address)
    
    # Wait a bit for the droplet to be fully ready
    time.sleep(30)
    
    add_droplet_to_firewall(api_token, droplet)