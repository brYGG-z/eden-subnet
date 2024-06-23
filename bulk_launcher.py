import asyncio
from time import sleep
import subprocess
import json
import os
import re
import shutil
from communex.compat.key import Ss58Address
from loguru import logger

# Set the environment variable
os.environ['COMX_YES_TO_ALL'] = 'true'
os.environ['COMX_OUTPUT_JSON'] = 'true'



def copy_and_rename_class(filename, original_classname, new_classname):
    with open(filename, 'r') as file:
        lines = file.readlines()

    class_found = False
    new_lines = []
    class_lines = []
    inside_class = False
    class_indent = None

    for line in lines:
        new_lines.append(line)
        if not class_found and re.match(rf'^\s*class {original_classname}', line):
            class_found = True
            inside_class = True
            class_indent = re.match(r"\s*", line).group()
        
        if inside_class:
            current_indent = re.match(r"\s*", line).group()
            if current_indent == "" and len(class_lines) > 0:
                inside_class = False
            else:
                class_lines.append(line)

    # Rename the copied class
    if class_lines:
        class_lines[0] = class_lines[0].replace(original_classname, new_classname, 1)
        new_lines.append("\n")
        new_lines.extend(class_lines)
        new_lines.append("\n")
    else:
        raise ValueError(f"Class {original_classname} not found in {filename}")

    # Write the new content back to the file
    with open(filename, 'w') as file:
        file.writelines(new_lines)

# Function to validate the module path
def module_path_check(module_path):
    try: 
        if re.match(r'^[a-zA-Z_]\w*(\.[a-zA-Z_]\w*)*$', module_path):
            filename, classname = module_path.split('.')
            return filename, classname
        else:
            print("Invalid characters in module path")
            return None, None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None


def serve_modules(module_path, source_module, port, NumModules, Netuid):

    for i in range(NumModules):

        # Separates by filename and classname (by the dot)
        filename, classname = module_path_check(module_path)
        classname_instance = f"{classname}_{i}"
        module_name = f"{module_path}_{i}"
        next_port = port

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

        # Creates a new class in the new miner file for this specific miner
        copy_and_rename_class(new_file_path, "Miner", classname_instance)

        print("Serving Miner")
        command = f'pm2 start "python -m eden_subnet.miner.{filename} --key_name {module_name} --host 0.0.0.0 --port {next_port}" --name "{module_name}"'
        os.system(command)
        print("Miner served.")

        next_port = port + i


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

def register(module_path, wan_ip, wan_ip_2, port, NumModules, Netuid, source_key, temp_stake, stake):

    ip = wan_ip

    for i in range(NumModules):
        if i == 10:
            ip = wan_ip_2
        key = source_key
        module_name = f"{module_path}_{i}"
        next_port = port + i
        ss58 = Ss58Address(module_name)
        print("Port: ", next_port)
        print("Transfer Com to new miner key")
        try:
            value = subprocess.run(["comx", "balance", "transfer", key, temp_stake, ss58], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(value.stdout)
        except Exception as e:
            logger.error(f"Error processing thing:\n{e}")
        sleep(10)

        print("Register new miner key")
        try:
            value = subprocess.run(["comx", "module", "register", "--ip", ip, "--port", f"{next_port}", "--stake", "300", module_name, module_name, "--netuid", f"{Netuid}"], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error registering miner, {e}")
        except Exception as e:
            logger.error(f"Error processing thing:\n{e}")        
        print(f"Registered {module_name} at {ip}:{next_port}")
        sleep(10)

        print("Remove Temp Stake from new miner")
        try:
            value = subprocess.run(["comx", "balance", "unstake",  module_name, temp_stake - stake, module_name, "--netuid", f"{Netuid}"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(value.stdout)
        except Exception as e:
            logger.error(f"Error processing thing:\n{e}")            
        print(f"Stake Removed")
        sleep(10)

        print("Send fund back from new miner")
        try:
            value = subprocess.run(["comx", "balance", "transfer",  module_name, temp_stake - stake - 0.5, source_key], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(value.stdout)
        except Exception as e:
            logger.error(f"Error processing thing:\n{e}")
        print(f"{temp_stake - stake - 0.5}COM returned to {source_key}")
        sleep(10)


        # Wait before repeating the registration process
        print("Register loop: f{i}")
        sleep(60)


if __name__ == "__main__":
    source_miner = "eden_subnet/miner/miner.py"
    source_validator = "eden_subnet/validator/validator.py"
    module_path = input("Enter module path: ")
    wan_ip = input("Enter WAN IP: ")
    wan_ip_2 = input("Enter 2nd WAN IP: ")
    source_key = input("Enter source key: ")
    temp_stake = input("Enter temp stake: ")
    stake = input("Enter stake: ")
    source_module = source_miner
    port = 50180
    NumModules = 20
    Netuid = 10

    serve_modules(
        module_path=module_path,
        source_module=source_module,
        port=port,
        NumModules=NumModules,
        Netuid=Netuid
    )

    register(
        module_path=module_path,
        wan_ip=wan_ip,
        wan_ip_2=wan_ip_2,
        port=port,
        NumModules=NumModules,
        Netuid=Netuid,
        source_key=source_key,
        temp_stake=temp_stake,
        stake=stake
    )


    
