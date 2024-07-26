import os
import re
import subprocess
import time
import digitalocean
import paramiko
import ipaddress

os.environ["DO_API_TOKEN"] = 'ENTER YOUR DIGITALOCEAN API TOKEN HERE'

class NginxRedirectSetup:
    def __init__(self):
        self.manager = None
        self.droplet = None
        self.ssh_key_path = None

    def get_api_token(self):
        token = os.environ.get('DO_API_TOKEN')
        if not token:
            token = input("Enter your DigitalOcean API token: ")
        return token

    def validate_ip_address(self, ip):
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def get_droplet_name(self):
        while True:
            name = input("Enter a name for the droplet (leave blank for default 'nginx-redirect'): ").strip()
            if not name:
                return "nginx-redirect"
            if re.match(r'^[a-zA-Z0-9-]+$', name):
                return name
            print("Invalid name. Use only letters, numbers, and hyphens.")

    def get_target_ip(self):
        while True:
            ip = input("Enter the target IP address: ")
            if self.validate_ip_address(ip):
                return ip
            print("Invalid IP address. Please try again.")

    def get_starting_port(self):
        while True:
            try:
                port = int(input("Enter the starting port number: "))
                if 1 <= port <= 65535:
                    return port
                print("Port number must be between 1 and 65535.")
            except ValueError:
                print("Invalid input. Please enter a number.")

    def get_num_redirects(self):
        while True:
            try:
                num = int(input("Enter the number of redirects (1-20): "))
                if 1 <= num <= 20:
                    return num
                print("Number of redirects must be between 1 and 20.")
            except ValueError:
                print("Invalid input. Please enter a number.")

    def get_ssh_key_choice(self):
        keys = self.manager.get_all_sshkeys()
        if not keys:
            print("No existing SSH keys found.")
            return "new"

        print("Existing SSH keys:")
        for i, key in enumerate(keys):
            print(f"{i+1}. {key.name}")
        
        print(f"{len(keys)+1}. Create a new key")

        while True:
            try:
                choice = int(input("Enter your choice: "))
                if 1 <= choice <= len(keys):
                    return keys[choice-1]
                elif choice == len(keys)+1:
                    return "new"
                print("Invalid choice. Please try again.")
            except ValueError:
                print("Invalid input. Please enter a number.")

    def create_new_ssh_key(self):
        key_name = input("Enter a name for the new SSH key: ")
        key_path = os.path.expanduser(f"~/.ssh/{key_name}")
        
        subprocess.run(["ssh-keygen", "-t", "rsa", "-b", "4096", "-f", key_path, "-N", ""])
        
        with open(f"{key_path}.pub", "r") as f:
            public_key = f.read().strip()
        
        try:
            key = digitalocean.SSHKey(token=self.manager.token,
                                      name=key_name,
                                      public_key=public_key)
            key.create()
            print(f"SSH key '{key_name}' added to DigitalOcean account.")
            return key, key_path
        except Exception as e:
            print(f"Error adding SSH key to DigitalOcean: {e}")
            return None, None

    def print_ssh_config_entry(self, name, ip_address):
        config_entry = f"""
    Host {name}
        HostName {ip_address}
        User root
        Port 22
    """
        print("\nSSH config entry for your droplet:")
        print(config_entry)
        print("You can copy this entry into your local SSH config file.")

    def create_droplet(self, ssh_keys, user_data, name):
        try:
            droplet = digitalocean.Droplet(
                token=self.manager.token,
                name=name,
                region="sfo3",
                image="nginx",
                size_slug="s-1vcpu-1gb",
                ssh_keys=ssh_keys,
                user_data=user_data
            )
            droplet.create()
            
            print("Waiting for droplet to be active...")
            actions = droplet.get_actions()
            for action in actions:
                action.wait()
            
            for _ in range(60):  # Wait up to 5 minutes
                droplet.load()
                if droplet.ip_address:
                    print(f"Droplet is active with IP: {droplet.ip_address}")
                    return droplet
                time.sleep(5)
            
            raise Exception("Timeout waiting for droplet IP address")
        except Exception as e:
            print(f"Error creating droplet: {e}")
            return None

    def create_reserved_ip(self):
        try:
            reserved_ip = digitalocean.FloatingIP(
                token=self.manager.token,
                droplet_id=self.droplet.id,
                region=self.droplet.region['slug']
            )
            reserved_ip.create()
            print(f"Reserved IP {reserved_ip.ip} assigned to droplet.")
            return reserved_ip.ip
        except Exception as e:
            print(f"Error creating reserved IP: {e}")
            return None

    def configure_nginx(self, target_ip, start_port, num_redirects, reserved_ip=None):
        try:
            if not self.ssh_key_path:
                self.ssh_key_path = os.path.expanduser("~/.ssh/id_rsa")
            
            print(f"Using SSH key: {self.ssh_key_path}")
            key = paramiko.RSAKey.from_private_key_file(self.ssh_key_path)
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            retries = 10
            for i in range(retries):
                try:
                    print(f"Attempting to connect to {self.droplet.ip_address}...")
                    time.sleep(15)
                    client.connect(hostname=self.droplet.ip_address, username="root", pkey=key, timeout=30, look_for_keys=False)
                    print("Connected successfully!")
                    break
                except Exception as e:
                    if i == retries - 1:
                        raise
                    print(f"Connection failed: {e}. Retrying in 30 seconds... ({i+1}/{retries})")
                    time.sleep(30)

            config = "events { worker_connections 1024; }\n\nhttp {\n"
            
            for i in range(num_redirects):
                port = start_port + i
                ip_to_use = self.droplet.ip_address if i < 10 or not reserved_ip else reserved_ip
                config += f"""
        server {{
            listen {port};
            server_name {ip_to_use};

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
            
            stdin, stdout, stderr = client.exec_command(f"echo '{config}' | sudo tee /etc/nginx/nginx.conf")
            print(stdout.read().decode())
            print(stderr.read().decode())
            
            stdin, stdout, stderr = client.exec_command("sudo systemctl restart nginx")
            print(stdout.read().decode())
            print(stderr.read().decode())
            
            client.close()
            print("NGINX configuration completed.")
        except Exception as e:
            print(f"Error configuring NGINX: {e}")

    def setup_nginx_redirect(self):
        token = self.get_api_token()
        self.manager = digitalocean.Manager(token=token)

        target_ip = self.get_target_ip()
        start_port = self.get_starting_port()
        num_redirects = self.get_num_redirects()

        ssh_key_choice = self.get_ssh_key_choice()
        if ssh_key_choice == "new":
            ssh_key, self.ssh_key_path = self.create_new_ssh_key()
            ssh_keys = [ssh_key] if ssh_key else []
        else:
            ssh_keys = [ssh_key_choice]
            self.ssh_key_path = os.path.expanduser(f"~/.ssh/{ssh_key_choice.name}")

        user_data = f"""#!/bin/bash
    sudo ufw allow {start_port}:{start_port + num_redirects - 1}/tcp
    sudo ufw allow {start_port}:{start_port + num_redirects - 1}/udp
    sudo ufw --force enable
    """

        droplet_name = self.get_droplet_name()
        self.droplet = self.create_droplet(ssh_keys, user_data, name=droplet_name)
        if not self.droplet or not self.droplet.ip_address:
            print("Failed to create droplet or get its IP address. Exiting.")
            return None, None, None, None

        print(f"Droplet created with IP: {self.droplet.ip_address}")

        self.print_ssh_config_entry(droplet_name, self.droplet.ip_address)

        reserved_ip = None
        if input("Do you want to create and assign a reserved IP? (y/n): ").lower() == 'y':
            reserved_ip = self.create_reserved_ip()

        self.configure_nginx(target_ip, start_port, num_redirects, reserved_ip)

        return self.droplet.ip_address, reserved_ip, start_port, num_redirects

def create_nginx_redirect():
    setup = NginxRedirectSetup()
    return setup.setup_nginx_redirect()

""" if __name__ == "__main__":
    ipv4, reserved_ip, starting_port, num_ports = create_nginx_redirect()
    print(f"Setup completed. IPv4: {ipv4}, Reserved IP: {reserved_ip}, Starting Port: {starting_port}, Number of Ports: {num_ports}") """