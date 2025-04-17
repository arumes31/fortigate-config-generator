from flask import Flask, request, render_template, jsonify
import json
import re
import logging
import os
import tempfile

# Clear all existing handlers to ensure clean logging setup
for handler in logging.root.handlers[:]:
    logging.root.handlers.remove(handler)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Configure loggers for Flask and Werkzeug
logger = logging.getLogger(__name__)
flask_logger = logging.getLogger('flask')
werkzeug_logger = logging.getLogger('werkzeug')

# Clear existing handlers for Flask and Werkzeug loggers
for handler in flask_logger.handlers[:]:
    flask_logger.handlers.remove(handler)
for handler in werkzeug_logger.handlers[:]:
    werkzeug_logger.handlers.remove(handler)

# Set levels and add StreamHandler to ensure consistent logging
flask_logger.setLevel(logging.DEBUG)
werkzeug_logger.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
flask_logger.addHandler(stream_handler)
werkzeug_logger.addHandler(stream_handler)

app = Flask(__name__)

# Log all incoming requests
@app.before_request
def log_request_info():
    logger.debug('Incoming request: %s %s from %s', request.method, request.path, request.remote_addr)
    logger.debug('Headers: %s', request.headers)
    if request.form:
        logger.debug('Form data: %s', dict(request.form))

# Log errors
@app.errorhandler(Exception)
def handle_exception(e):
    logger.error('Unhandled exception: %s', str(e), exc_info=True)
    return jsonify({"error": "Internal server error"}), 500

# Predefined service templates
SERVICE_TEMPLATES = {
    "HTTP": {"protocol": "TCP", "port": "80"},
    "HTTPS": {"protocol": "TCP", "port": "443"},
    "SSH": {"protocol": "TCP", "port": "22"},
    "DNS": {"protocol": "UDP", "port": "53"},
    "RDP": {"protocol": "TCP", "port": "3389"}
}

# Predefined service group templates
SERVICE_GROUP_TEMPLATES = {
    "Web": ["HTTP", "HTTPS"],
    "Admin": ["SSH", "RDP"],
    "DNS-Group": ["DNS"]
}

# Endpoint to receive frontend logs
@app.route('/log', methods=['POST'])
def log_frontend():
    logger.debug("Received frontend log request")
    data = request.get_json()
    if not data:
        logger.warning("No JSON data in frontend log request")
        return jsonify({"status": "error", "message": "No data provided"}), 400
    message = data.get('message', 'No message provided')
    logger.debug('Frontend log: %s', message)
    return jsonify({"status": "logged"})

@app.route('/')
def index():
    logger.debug("Rendering index page")
    return render_template('index.html', service_templates=SERVICE_TEMPLATES, group_templates=SERVICE_GROUP_TEMPLATES)

@app.route('/generate_policy', methods=['POST'])
def generate_policy():
    logger.debug("Received request to generate policy")
    data = request.form
    policy_name = data.get('policy_name', 'policy')
    policy_comment = data.get('policy_comment', 'policy')
    src_interfaces = data.getlist('src_interfaces[]')
    dst_interfaces = data.getlist('dst_interfaces[]')
    src_addresses = data.getlist('src_addresses[]')
    dst_addresses = data.getlist('dst_addresses[]')
    services = json.loads(data.get('services', '[]'))
    action = data.get('action', 'accept')
    nat = data.get('nat', 'enable')
    
    # Log input data
    logger.debug(f"Policy Name: {policy_name}")
    logger.debug(f"Policy Comment: {policy_comment}")
    logger.debug(f"Source Interfaces: {src_interfaces}")
    logger.debug(f"Destination Interfaces: {dst_interfaces}")
    logger.debug(f"Source Addresses: {src_addresses}")
    logger.debug(f"Destination Addresses: {dst_addresses}")
    logger.debug(f"Services: {services}")
    logger.debug(f"Action: {action}")
    logger.debug(f"NAT: {nat}")
    
    # Extract service names based on type
    service_names = []
    for svc in services:
        if svc['type'] == 'group':
            service_names.append(svc['name'])
        elif svc['type'] == 'template':
            service_names.append(svc['name'])
        else:
            # Custom service
            svc_name = f"custom_{svc['name']}"
            service_names.append(svc_name)
    
    # Helper function to generate a single policy
    def generate_single_policy(policy_name, policy_comment, src_intfs, dst_intfs, src_addrs, dst_addrs, svc_names, action, nat, include_custom_services=True):
        cli_commands = "config firewall policy\n"
        cli_commands += "edit 0\n"
        cli_commands += f'set name "{policy_name}"\n'
        cli_commands += f'set comments "{policy_comment}"\n'
        cli_commands += "set srcintf " + " ".join([f'"{intf}"' for intf in src_intfs]) + "\n"
        cli_commands += "set dstintf " + " ".join([f'"{intf}"' for intf in dst_intfs]) + "\n"
        cli_commands += "set srcaddr " + " ".join([f'"{addr}"' for addr in src_addrs]) + "\n"
        cli_commands += "set dstaddr " + " ".join([f'"{addr}"' for addr in dst_addrs]) + "\n"

        # Add custom service definitions if needed
        if include_custom_services:
            for svc in services:
                if svc['type'] == 'custom' and f"custom_{svc['name']}" in svc_names:
                    svc_name = f"custom_{svc['name']}"
                    cli_commands += "config firewall service custom\n"
                    cli_commands += f'edit "{svc_name}"\n'
                    cli_commands += f"set {svc['protocol'].lower()} {svc['port']}\n"
                    cli_commands += "next\nend\n"
        
        cli_commands += "set service " + " ".join([f'"{svc}"' for svc in svc_names]) + "\n"
        cli_commands += f'set action {action}\n'
        cli_commands += 'set schedule "always"\n'
        cli_commands += f'set nat {nat}\n'
        cli_commands += "next\nend\n"
        return cli_commands
    
    # Output 1: All interfaces and services in one policy
    output1 = generate_single_policy(
        policy_name=policy_name,
        policy_comment=policy_comment,
        src_intfs=src_interfaces,
        dst_intfs=dst_interfaces,
        src_addrs=src_addresses,
        dst_addrs=dst_addresses,
        svc_names=service_names,
        action=action,
        nat=nat
    )
    logger.debug("Output 1 (All in one policy):\n%s", output1)
    
    # Output 2: One policy per service, with all interfaces
    output2 = ""
    for svc in service_names:
        policy_name_svc = f"{policy_name}-{svc}"
        output2 += generate_single_policy(
            policy_name=policy_name_svc,
            policy_comment=policy_comment,
            src_intfs=src_interfaces,
            dst_intfs=dst_interfaces,
            src_addrs=src_addresses,
            dst_addrs=dst_addresses,
            svc_names=[svc],
            action=action,
            nat=nat,
            include_custom_services=True
        )
        output2 += "\n"  # Separate policies with a newline
    logger.debug("Output 2 (One policy per service):\n%s", output2)
    
    # Output 3: One policy per source interface, destination interface, and service
    output3 = ""
    for src_intf in src_interfaces:
        for dst_intf in dst_interfaces:
            for svc in service_names:
                policy_name_intf_svc = f"{policy_name}-{src_intf}-{dst_intf}-{svc}"
                output3 += generate_single_policy(
                    policy_name=policy_name_intf_svc,
                    policy_comment=policy_comment,
                    src_intfs=[src_intf],
                    dst_intfs=[dst_intf],
                    src_addrs=src_addresses,
                    dst_addrs=dst_addresses,
                    svc_names=[svc],
                    action=action,
                    nat=nat,
                    include_custom_services=True
                )
                output3 += "\n"  # Separate policies with a newline
    logger.debug("Output 3 (One policy per src interface, dst interface, and service):\n%s", output3)
    
    # Combine all outputs into the response
    response = {
        "output1": output1,
        "output2": output2,
        "output3": output3
    }
    logger.debug("Returning response with all outputs")
    return jsonify(response)

@app.route('/parse_config', methods=['POST'])
def parse_config():
    logger.debug("Received request to parse config")
    if 'config_file' not in request.files:
        logger.error("No file uploaded")
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['config_file']

    # Save file to a temp location
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, file.filename)
    file.save(temp_path)

    # Read content
    with open(temp_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Delete file after parsing
    try:
        os.remove(temp_path)
        logger.debug(f"Temporary config file {temp_path} deleted")
    except Exception as e:
        logger.warning(f"Failed to delete temp file {temp_path}: {e}")
    logger.debug("Config file content length: %d bytes", len(content))
    
    # Log a snippet of the config file for debugging (first 500 characters)
    logger.debug("Config file snippet (first 500 chars):\n%s", content[:500])
    
    # Find and log the config system interface section
    interface_section_match = re.search(r'config system interface\s*(.*?)\s*end', content, re.DOTALL)
    if interface_section_match:
        interface_section = interface_section_match.group(0)
        logger.debug("Found config system interface section:\n%s", interface_section)
    else:
        logger.warning("No config system interface section found in the config file")
    
    # Find and log the config firewall address section
    address_section_match = re.search(r'config firewall address\s*(.*?)\s*end', content, re.DOTALL)
    if address_section_match:
        address_section = address_section_match.group(0)
        logger.debug("Found config firewall address section:\n%s", address_section)
    else:
        logger.warning("No config firewall address section found in the config file")
    
    interfaces = []
    addresses = []
    services = []
    service_groups = {}
    
    # Parse interfaces
    interface_pattern = re.compile(r'config system interface\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in interface_pattern.finditer(content):
        interface_name = match.group(1)
        interfaces.append(interface_name)
        logger.debug("Found interface: %s", interface_name)
    
    # Fallback for interfaces
    if not interfaces or len(interfaces) == 1:
        logger.debug("Falling back to line-by-line interface parsing")
        lines = content.splitlines()
        inside_interface_section = False
        for line in lines:
            line = line.strip()
            if line.startswith('config system interface'):
                inside_interface_section = True
                continue
            if line.startswith('end') and inside_interface_section:
                inside_interface_section = False
                continue
            if inside_interface_section and line.startswith('edit '):
                match = re.match(r'edit\s+"([^"]+)"', line)
                if match:
                    interface_name = match.group(1)
                    if interface_name not in interfaces:
                        interfaces.append(interface_name)
                        logger.debug("Found interface (fallback): %s", interface_name)
    
    logger.debug("Parsed interfaces: %s", interfaces)
    
    # Parse addresses
    address_pattern = re.compile(r'config firewall address\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in address_pattern.finditer(content):
        address_name = match.group(1)
        addresses.append(address_name)
        logger.debug("Found address: %s", address_name)
    
    # Fallback for addresses
    if not addresses or len(addresses) == 1:
        logger.debug("Falling back to line-by-line address parsing")
        lines = content.splitlines()
        inside_address_section = False
        for line in lines:
            line = line.strip()
            if line.startswith('config firewall address'):
                inside_address_section = True
                continue
            if line.startswith('end') and inside_address_section:
                inside_address_section = False
                continue
            if inside_address_section and line.startswith('edit '):
                match = re.match(r'edit\s+"([^"]+)"', line)
                if match:
                    address_name = match.group(1)
                    if address_name not in addresses:
                        addresses.append(address_name)
                        logger.debug("Found address (fallback): %s", address_name)
    
    logger.debug("Parsed addresses: %s", addresses)
    
    # Parse services from policy definitions
    service_pattern = re.compile(r'set service\s+"([^"]+)"', re.DOTALL)
    service_set = set()
    for match in service_pattern.finditer(content):
        services_list = [s.strip('"') for s in match.group(1).split()]
        service_set.update(services_list)
    for service_name in service_set:
        if service_name.startswith(('TCP', 'UDP')):
            protocol = service_name[:3]
            port = service_name[3:]
            services.append({"name": service_name, "protocol": protocol, "port": port})
        else:
            services.append({"name": service_name, "protocol": "UNKNOWN", "port": "0"})
    logger.debug("Parsed services: %s", services)
    
    # Parse service groups
    service_group_pattern = re.compile(r'config firewall service group\s+edit\s+"([^"]+)"\s+set member\s+([^\n]+)\s+next', re.DOTALL)
    for match in service_group_pattern.finditer(content):
        group_name = match.group(1)
        members = [m.strip('"') for m in match.group(2).split()]
        service_groups[group_name] = members
    # Fallback: Infer service groups from policy references
    group_ref_pattern = re.compile(r'set service\s+"([^"]+)"', re.DOTALL)
    for match in group_ref_pattern.finditer(content):
        service_names = [s.strip('"') for s in match.group(1).split()]
        for name in service_names:
            if ' ' in match.group(1) and name not in service_groups:
                members = [s for s in service_names if s in SERVICE_TEMPLATES or s in [svc['name'] for svc in services]]
                if members and len(members) > 1:
                    inferred_group_name = match.group(1).strip('"').replace(' ', '-')
                    service_groups[inferred_group_name] = members
    logger.debug("Parsed service groups: %s", service_groups)
    
    # Log the response being sent
    response = {
        "interfaces": interfaces,
        "addresses": addresses,
        "services": services,
        "service_groups": service_groups
    }
    logger.debug("Returning parsed config response: %s", response)
    
    return jsonify(response)

if __name__ == '__main__':
    logger.info("Starting Flask application on host 0.0.0.0, port 5000")
    # Test frontend logging endpoint at startup
    import requests
    try:
        requests.post('http://localhost:5000/log', json={"message": "Test log at startup"})
    except Exception as e:
        logger.error("Failed to send test log at startup: %s", str(e))
    app.run(host='0.0.0.0', port=5000, debug=False)