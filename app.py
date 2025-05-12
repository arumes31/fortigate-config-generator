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

# Template storage file (in persistent volume)
TEMPLATE_FILE = '/app/data/templates.json'

# Ensure the templates.json file exists
def ensure_template_file():
    if not os.path.exists(TEMPLATE_FILE):
        os.makedirs(os.path.dirname(TEMPLATE_FILE), exist_ok=True)
        with open(TEMPLATE_FILE, 'w') as f:
            json.dump([], f)
        logger.debug(f"Created empty templates file at {TEMPLATE_FILE}")

# Load existing templates or initialize empty list
def load_templates():
    ensure_template_file()
    with open(TEMPLATE_FILE, 'r') as f:
        return json.load(f)

# Save templates
def save_templates(templates):
    with open(TEMPLATE_FILE, 'w') as f:
        json.dump(templates, f, indent=4)

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

@app.route('/save_template', methods=['POST'])
def save_template():
    logger.debug("Received request to save template")
    data = request.form
    template_name = data.get('template_name')
    if not template_name:
        logger.error("No template name provided")
        return jsonify({"error": "Template name is required"}), 400

    # Explicitly capture all form fields, including empty ones
    template_data = {
        'policy_name': data.get('policy_name', ''),
        'policy_comment': data.get('policy_comment', ''),
        'src_interfaces': data.getlist('src_interfaces[]') or [],
        'dst_interfaces': data.getlist('dst_interfaces[]') or [],
        'src_addresses': data.getlist('src_addresses[]') or [],
        'dst_addresses': data.getlist('dst_addresses[]') or [],
        'services': json.loads(data.get('services', '[]')) or [],
        'action': data.get('action', ''),
        'ssl_ssh_profile': data.get('ssl_ssh_profile', ''),
        'webfilter_profile': data.get('webfilter_profile', ''),
        'application_list': data.get('application_list', ''),
        'ips_sensor': data.get('ips_sensor', ''),
        'logtraffic': data.get('logtraffic', ''),
        'logtraffic_start': data.get('logtraffic_start', ''),
        'auto_asic_offload': data.get('auto_asic_offload', ''),
        'nat': data.get('nat', '')
    }

    templates = load_templates()
    templates = [t for t in templates if t['name'] != template_name]
    templates.append({'name': template_name, 'data': template_data})

    save_templates(templates)
    logger.debug(f"Template '{template_name}' saved with data: {template_data}")
    return jsonify({"status": "success", "message": f"Template '{template_name}' saved"})

@app.route('/load_templates', methods=['GET'])
def load_templates_endpoint():
    logger.debug("Received request to load templates")
    templates = load_templates()
    template_names = [t['name'] for t in templates]
    logger.debug(f"Available templates: {template_names}")
    return jsonify({"templates": template_names})

@app.route('/get_template/<template_name>', methods=['GET'])
def get_template(template_name):
    logger.debug(f"Received request to get template: {template_name}")
    templates = load_templates()
    for template in templates:
        if template['name'] == template_name:
            logger.debug(f"Template '{template_name}' found")
            return jsonify({"status": "success", "data": template['data']})
    logger.error(f"Template '{template_name}' not found")
    return jsonify({"error": "Template not found"}), 404

@app.route('/delete_template/<template_name>', methods=['DELETE'])
def delete_template(template_name):
    logger.debug(f"Received request to delete template: {template_name}")
    templates = load_templates()
    original_length = len(templates)
    templates = [t for t in templates if t['name'] != template_name]
    if len(templates) < original_length:
        save_templates(templates)
        logger.debug(f"Template '{template_name}' deleted")
        return jsonify({"status": "success", "message": f"Template '{template_name}' deleted"})
    logger.error(f"Template '{template_name}' not found")
    return jsonify({"error": "Template not found"}), 404

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
    ssl_ssh_profile = data.get('ssl_ssh_profile', '')
    webfilter_profile = data.get('webfilter_profile', '')
    application_list = data.get('application_list', '')
    ips_sensor = data.get('ips_sensor', '')  # Corrected line
    logtraffic = data.get('logtraffic', 'all')
    logtraffic_start = data.get('logtraffic_start', 'enable')
    auto_asic_offload = data.get('auto_asic_offload', 'enable')
    nat = data.get('nat', 'enable')

    # Rest of the function remains unchanged
    logger.debug(f"Policy Name: {policy_name}")
    logger.debug(f"Policy Comment: {policy_comment}")
    logger.debug(f"Source Interfaces: {src_interfaces}")
    logger.debug(f"Destination Interfaces: {dst_interfaces}")
    logger.debug(f"Source Addresses: {src_addresses}")
    logger.debug(f"Destination Addresses: {dst_addresses}")
    logger.debug(f"Services: {services}")
    logger.debug(f"Action: {action}")
    logger.debug(f"SSL/SSH Profile: {ssl_ssh_profile}")
    logger.debug(f"Webfilter Profile: {webfilter_profile}")
    logger.debug(f"Application List: {application_list}")
    logger.debug(f"IPS Sensor: {ips_sensor}")
    logger.debug(f"Log Traffic: {logtraffic}")
    logger.debug(f"Log Traffic Start: {logtraffic_start}")
    logger.debug(f"Auto ASIC Offload: {auto_asic_offload}")
    logger.debug(f"NAT: {nat}")

    service_names = []
    for svc in services:
        if svc['type'] == 'group':
            service_names.append(svc['name'])
        elif svc['type'] == 'template':
            service_names.append(svc['name'])
        else:
            svc_name = f"custom_{svc['name']}"
            service_names.append(svc_name)

    def generate_single_policy(policy_name, policy_comment, src_intfs, dst_intfs, src_addrs, dst_addrs, svc_names, action, ssl_ssh_profile, webfilter_profile, application_list, ips_sensor, logtraffic, logtraffic_start, auto_asic_offload, nat, include_custom_services=True):
        cli_commands = "config firewall policy\n"
        cli_commands += "edit 0\n"
        cli_commands += f'set name "{policy_name}"\n'
        cli_commands += f'set comments "{policy_comment}"\n'
        cli_commands += "set srcintf " + " ".join([f'"{intf}"' for intf in src_intfs]) + "\n"
        cli_commands += "set dstintf " + " ".join([f'"{intf}"' for intf in dst_intfs]) + "\n"
        cli_commands += "set srcaddr " + " ".join([f'"{addr}"' for addr in src_addrs]) + "\n"
        cli_commands += "set dstaddr " + " ".join([f'"{addr}"' for addr in dst_addrs]) + "\n"

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
        if ssl_ssh_profile or webfilter_profile or application_list or ips_sensor:
            cli_commands += 'set utm-status enable\n'
        if ssl_ssh_profile:
            cli_commands += f'set ssl-ssh-profile "{ssl_ssh_profile}"\n'
        if webfilter_profile:
            cli_commands += f'set webfilter-profile "{webfilter_profile}"\n'
        if application_list:
            cli_commands += f'set application-list "{application_list}"\n'
        if ips_sensor:
            cli_commands += f'set ips-sensor "{ips_sensor}"\n'
        cli_commands += f'set logtraffic {logtraffic}\n'
        cli_commands += f'set logtraffic-start {logtraffic_start}\n'
        cli_commands += f'set auto-asic-offload {auto_asic_offload}\n'
        cli_commands += f'set nat {nat}\n'
        cli_commands += "next\nend\n"
        return cli_commands

    output1 = generate_single_policy(
        policy_name=policy_name,
        policy_comment=policy_comment,
        src_intfs=src_interfaces,
        dst_intfs=dst_interfaces,
        src_addrs=src_addresses,
        dst_addrs=dst_addresses,
        svc_names=service_names,
        action=action,
        ssl_ssh_profile=ssl_ssh_profile,
        webfilter_profile=webfilter_profile,
        application_list=application_list,
        ips_sensor=ips_sensor,
        logtraffic=logtraffic,
        logtraffic_start=logtraffic_start,
        auto_asic_offload=auto_asic_offload,
        nat=nat
    )
    logger.debug("Output 1 (All in one policy):\n%s", output1)

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
            ssl_ssh_profile=ssl_ssh_profile,
            webfilter_profile=webfilter_profile,
            application_list=application_list,
            ips_sensor=ips_sensor,
            logtraffic=logtraffic,
            logtraffic_start=logtraffic_start,
            auto_asic_offload=auto_asic_offload,
            nat=nat,
            include_custom_services=True
        )
        output2 += "\n"
    logger.debug("Output 2 (One policy per service):\n%s", output2)

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
                    ssl_ssh_profile=ssl_ssh_profile,
                    webfilter_profile=webfilter_profile,
                    application_list=application_list,
                    ips_sensor=ips_sensor,
                    logtraffic=logtraffic,
                    logtraffic_start=logtraffic_start,
                    auto_asic_offload=auto_asic_offload,
                    nat=nat,
                    include_custom_services=True
                )
                output3 += "\n"
    logger.debug("Output 3 (One policy per src interface, dst interface, and service):\n%s", output3)

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
        logger.error("No file loaded")
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['config_file']
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, file.filename)
    file.save(temp_path)

    with open(temp_path, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        os.remove(temp_path)
        logger.debug(f"Temporary config file {temp_path} deleted")
    except Exception as e:
        logger.warning(f"Failed to delete temp file {temp_path}: {e}")
    logger.debug("Config file content length: %d bytes", len(content))

    logger.debug("Config file snippet (first 500 chars):\n%s", content[:500])

    interfaces = []
    addresses = []
    services = []
    service_groups = {}
    ssl_ssh_profiles = []
    webfilter_profiles = []
    application_lists = []
    ips_sensors = []

    # Parse interfaces (unchanged)
    interface_pattern = re.compile(r'config system interface\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in interface_pattern.finditer(content):
        interface_name = match.group(1)
        interfaces.append(interface_name)
        logger.debug("Found interface: %s", interface_name)

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

    # Parse address groups
    addrgrp_pattern = re.compile(r'config firewall addrgrp\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in addrgrp_pattern.finditer(content):
        addrgrp_name = match.group(1)
        if addrgrp_name not in addresses:
            addresses.append(addrgrp_name)
            logger.debug("Found address group: %s", addrgrp_name)

    # Fallback parsing for addresses and address groups
    if not addresses or len(addresses) == 1:
        logger.debug("Falling back to line-by-line address and address group parsing")
        lines = content.splitlines()
        inside_address_section = False
        inside_addrgrp_section = False
        for line in lines:
            line = line.strip()
            if line.startswith('config firewall address'):
                inside_address_section = True
                continue
            if line.startswith('config firewall addrgrp'):
                inside_addrgrp_section = True
                continue
            if line.startswith('end') and (inside_address_section or inside_addrgrp_section):
                inside_address_section = False
                inside_addrgrp_section = False
                continue
            if (inside_address_section or inside_addrgrp_section) and line.startswith('edit '):
                match = re.match(r'edit\s+"([^"]+)"', line)
                if match:
                    address_name = match.group(1)
                    if address_name not in addresses:
                        addresses.append(address_name)
                        logger.debug("Found %s (fallback): %s", "address group" if inside_addrgrp_section else "address", address_name)

    # Parse addresses from firewall policies as fallback
    policy_addr_pattern = re.compile(r'set (?:srcaddr|dstaddr)\s+((?:"[^"]+"\s*)+)', re.DOTALL)
    for match in policy_addr_pattern.finditer(content):
        addr_list = [addr.strip('"') for addr in match.group(1).split()]
        for addr in addr_list:
            if addr not in addresses:
                addresses.append(addr)
                logger.debug("Found address from policy: %s", addr)

    logger.debug("Final parsed addresses: %s", addresses)

    # Parse services (improved regex and fallback)
    service_pattern = re.compile(
        r'config firewall service custom\s+edit\s+"([^"]+)"\s+((?:set\s+[^\n]+\n)*)\s+next',
        re.DOTALL
    )
    for match in service_pattern.finditer(content):
        service_name = match.group(1)
        service_config = match.group(2)
        protocol = 'TCP'  # Default protocol
        port = '0'        # Default port

        # Try to extract protocol and port
        protocol_match = re.search(r'set\s+(\w+)\s+([^\n]+)', service_config)
        if protocol_match:
            protocol = protocol_match.group(1).upper()
            port = protocol_match.group(2).strip()
        else:
            # Fallback: look for common attributes
            if 'tcp' in service_config.lower():
                protocol = 'TCP'
            elif 'udp' in service_config.lower():
                protocol = 'UDP'
            port_match = re.search(r'\b\d+\b', service_config)
            if port_match:
                port = port_match.group(0)

        services.append({"name": service_name, "protocol": protocol, "port": port})
        logger.debug("Found service: %s (protocol: %s, port: %s)", service_name, protocol, port)

    # Fallback: Parse services from firewall policies
    policy_service_pattern = re.compile(r'set service\s+((?:"[^"]+"\s*)+)', re.DOTALL)
    for match in policy_service_pattern.finditer(content):
        svc_list = [svc.strip('"') for svc in match.group(1).split()]
        for svc in svc_list:
            if svc not in [s['name'] for s in services] and svc not in service_groups:
                # Assume unknown services are TCP with port 0 (generic)
                services.append({"name": svc, "protocol": "TCP", "port": "0"})
                logger.debug("Found service from policy (fallback): %s (protocol: TCP, port: 0)", svc)

    # Parse service groups (unchanged)
    service_group_pattern = re.compile(r'config firewall service group\s+edit\s+"([^"]+)"\s+set member\s+([^\n]+)\s+next', re.DOTALL)
    for match in service_group_pattern.finditer(content):
        group_name = match.group(1)
        members = [m.strip('"') for m in match.group(2).split()]
        service_groups[group_name] = members
        logger.debug("Found service group: %s with members: %s", group_name, members)

    # Parse SSL/SSH profiles (unchanged)
    ssl_ssh_pattern = re.compile(r'config firewall ssl-ssh-profile\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in ssl_ssh_pattern.finditer(content):
        profile_name = match.group(1)
        ssl_ssh_profiles.append(profile_name)
        logger.debug("Found SSL/SSH profile: %s", profile_name)

    # Parse webfilter profiles (unchanged)
    webfilter_pattern = re.compile(r'config webfilter profile\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in webfilter_pattern.finditer(content):
        profile_name = match.group(1)
        webfilter_profiles.append(profile_name)
        logger.debug("Found webfilter profile: %s", profile_name)

    # Parse application lists (unchanged)
    application_pattern = re.compile(r'config application list\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in application_pattern.finditer(content):
        list_name = match.group(1)
        application_lists.append(list_name)
        logger.debug("Found application list: %s", list_name)

    # Parse IPS sensors (unchanged)
    ips_pattern = re.compile(r'config ips sensor\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in ips_pattern.finditer(content):
        sensor_name = match.group(1)
        ips_sensors.append(sensor_name)
        logger.debug("Found IPS sensor: %s", sensor_name)

    response = {
        "interfaces": interfaces,
        "addresses": addresses,
        "services": services,
        "service_groups": service_groups,
        "ssl_ssh_profiles": ssl_ssh_profiles,
        "webfilter_profiles": webfilter_profiles,
        "application_lists": application_lists,
        "ips_sensors": ips_sensors
    }
    logger.debug("Returning parsed config response: %s", response)

    return jsonify(response)

if __name__ == '__main__':
    logger.info("Starting Flask application on host 0.0.0.0, port 5000")
    import requests
    try:
        requests.post('http://localhost:5000/log', json={"message": "Test log at startup"})
    except Exception as e:
        logger.error("Failed to send test log at startup: %s", str(e))
    app.run(host='0.0.0.0', port=5000, debug=False)