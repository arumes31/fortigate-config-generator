# app.py (Version 1.8)
from flask import Flask, request, render_template, jsonify, redirect, send_file
import json
import re
import logging
import os
import tempfile
import uuid
import string
import random
from urllib.parse import urlparse
import sqlite3
from io import BytesIO

# Configure logging
for handler in logging.root.handlers[:]:
    logging.root.handlers.remove(handler)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)
flask_logger = logging.getLogger('flask')
werkzeug_logger = logging.getLogger('werkzeug')

for handler in flask_logger.handlers[:]:
    flask_logger.handlers.remove(handler)
for handler in werkzeug_logger.handlers[:]:
    werkzeug_logger.handlers.remove(handler)

flask_logger.setLevel(logging.DEBUG)
werkzeug_logger.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
flask_logger.addHandler(stream_handler)
werkzeug_logger.addHandler(stream_handler)

app = Flask(__name__)

# SQLite database setup
DB_PATH = '/app/data/database.db'

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            name TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS short_urls (
            short_code TEXT PRIMARY KEY,
            url TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS last_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_data TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    logger.debug("SQLite database initialized at %s", DB_PATH)

# Initialize database
init_db()

# Get TRUSTED_DOMAIN from environment variable
TRUSTED_DOMAIN = os.getenv('TRUSTED_DOMAIN')
if not TRUSTED_DOMAIN:
    logger.error("TRUSTED_DOMAIN environment variable not set")
    raise ValueError("TRUSTED_DOMAIN environment variable is required")

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

# Known services with correct ports
KNOWN_SERVICES = {
    "HTTP": {"protocol": "TCP", "port": "80"},
    "HTTPS": {"protocol": "TCP", "port": "443"},
    "SSH": {"protocol": "TCP", "port": "22"},
    "DNS": {"protocol": "UDP", "port": "53"},
    "RDP": {"protocol": "TCP", "port": "3389"},
    "ALL_ICMP": {"protocol": "ICMP", "port": "0"},
    "ALL_ICMP6": {"protocol": "ICMP6", "port": "0"},
    "PING": {"protocol": "ICMP", "port": "0"},
    "RADIUS": {"protocol": "UDP", "port": "1812"},
    "SMB": {"protocol": "TCP", "port": "445"},
    "SAMBA": {"protocol": "TCP", "port": "445"},
    "SMTP": {"protocol": "TCP", "port": "25"},
    "SMTPS": {"protocol": "TCP", "port": "465"},
    "IMAP": {"protocol": "TCP", "port": "143"},
    "IMAPS": {"protocol": "TCP", "port": "993"},
    "NTP": {"protocol": "UDP", "port": "123"}
}

# Load templates from SQLite
def load_templates():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT name, data FROM templates')
    rows = cursor.fetchall()
    templates = []
    for name, data in rows:
        try:
            # Validate template name: ensure it doesn't contain invalid characters
            if not isinstance(name, str) or not name.strip() or any(c in name for c in '"\n\r\t'):
                logger.warning(f"Skipping template with invalid name: {name}")
                continue
            # Parse the JSON data
            parsed_data = json.loads(data)
            if not isinstance(parsed_data, dict):
                logger.warning(f"Skipping template '{name}' due to invalid data format: {data}")
                continue
            templates.append({'name': name, 'data': parsed_data})
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON data for template '{name}': {str(e)}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error while processing template '{name}': {str(e)}")
            continue
    conn.close()
    logger.debug("Loaded %d templates from SQLite", len(templates))
    return templates

# Save templates to SQLite
def save_templates(templates):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM templates')  # Clear existing templates
    for template in templates:
        cursor.execute('INSERT INTO templates (name, data) VALUES (?, ?)',
                       (template['name'], json.dumps(template['data'])))
    conn.commit()
    conn.close()
    logger.debug("Saved %d templates to SQLite", len(templates))

# Load short URL mappings from SQLite
def load_short_urls():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT short_code, url FROM short_urls')
    short_urls = {short_code: url for short_code, url in cursor.fetchall()}
    conn.close()
    logger.debug("Loaded %d short URLs from SQLite", len(short_urls))
    return short_urls

# Save short URL mappings to SQLite
def save_short_urls(short_urls):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM short_urls')  # Clear existing short URLs
    for short_code, url in short_urls.items():
        cursor.execute('INSERT INTO short_urls (short_code, url) VALUES (?, ?)',
                       (short_code, url))
    conn.commit()
    conn.close()
    logger.debug("Saved %d short URLs to SQLite", len(short_urls))

# Load last config from SQLite
def load_last_config():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT config_data FROM last_config ORDER BY id DESC LIMIT 1')
    result = cursor.fetchone()
    conn.close()
    if result:
        logger.debug("Loaded last config from SQLite")
        return json.loads(result[0])
    logger.debug("No last config found in SQLite")
    return None

# Save last config to SQLite
def save_last_config(config):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM last_config')  # Keep only the latest config
    cursor.execute('INSERT INTO last_config (config_data) VALUES (?)', (json.dumps(config),))
    conn.commit()
    conn.close()
    logger.debug("Saved last config to SQLite")

# Generate a random short code
def generate_short_code(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Validate URL domain against TRUSTED_DOMAIN
def is_trusted_domain(url):
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        if not domain:
            return parsed_url.path.startswith('/') and not parsed_url.path.startswith('//')
        return domain == TRUSTED_DOMAIN.lower() or domain.endswith('.' + TRUSTED_DOMAIN.lower())
    except Exception as e:
        logger.error(f"Error parsing URL {url}: {e}")
        return False

# Endpoint to shorten a URL (only for templates)
@app.route('/shorten_url', methods=['POST'])
def shorten_url():
    logger.debug("Received request to shorten URL")
    data = request.get_json()
    if not data or 'url' not in data:
        logger.warning("No URL provided in shorten_url request")
        return jsonify({"error": "URL is required"}), 400

    original_url = data['url']

    # If the URL is relative and starts with /get_template/, prepend request.host_url
    if original_url.startswith('/get_template/'):
        original_url = f"{request.host_url.rstrip('/')}{original_url}"
        logger.debug(f"Constructed full URL: {original_url}")
    
    # Check if URL is related to templates
    if not original_url.startswith(f"{request.host_url}get_template/"):
        logger.warning(f"URL {original_url} is not a template URL")
        return jsonify({"error": "Short URLs are only allowed for templates"}), 403

    if not is_trusted_domain(original_url):
        logger.warning(f"URL {original_url} does not match TRUSTED_DOMAIN {TRUSTED_DOMAIN}")
        return jsonify({"error": f"URL must belong to trusted domain: {TRUSTED_DOMAIN}"}), 403

    short_urls = load_short_urls()

    for short_code, url in short_urls.items():
        if url == original_url:
            logger.debug(f"Found existing short URL for {original_url}")
            return jsonify({"status": "success", "short_code": short_code})

    while True:
        short_code = generate_short_code()
        if short_code not in short_urls:
            break

    short_urls[short_code] = original_url
    save_short_urls(short_urls)
    logger.debug(f"Generated short URL with code: {short_code} for {original_url}")
    return jsonify({"status": "success", "short_code": short_code})

# Endpoint to redirect short URLs
@app.route('/s/<short_code>')
def redirect_short_url(short_code):
    logger.debug(f"Processing short URL redirect for code: {short_code}")
    try:
        short_urls = load_short_urls()
        logger.debug(f"Loaded short URLs: {len(short_urls)} entries")
        # Log anonymized short_urls keys for debugging (avoid logging full URLs)
        logger.debug(f"Available short codes: {list(short_urls.keys())}")
        original_url = short_urls.get(short_code)
        if not original_url:
            logger.error(f"Short code {short_code} not found in short_urls")
            return jsonify({"error": "Short URL not found"}), 404
        
        # Normalize original_url to handle trailing slashes
        original_url = original_url.rstrip('/')
        logger.debug(f"Found original URL: {original_url} for short code: {short_code}")
        if not is_trusted_domain(original_url):
            logger.warning(f"Stored URL {original_url} for short code {short_code} does not match TRUSTED_DOMAIN {TRUSTED_DOMAIN}")
            return jsonify({"error": f"Redirect URL does not belong to trusted domain: {TRUSTED_DOMAIN}"}), 403

        # Extract template name from the URL (e.g., /get_template/Test2 -> Test2)
        template_name = None
        expected_prefix = f"{request.host_url.rstrip('/')}/get_template/"
        if original_url.startswith(expected_prefix):
            template_name = original_url[len(expected_prefix):].lstrip('/')
            logger.debug(f"Extracted template name: {template_name} from URL: {original_url}")
        else:
            logger.error(f"Invalid template URL format: {original_url}. Expected prefix: {expected_prefix}")
            return jsonify({"error": "Invalid template URL format in short URL"}), 400

        if not template_name:
            logger.error(f"Could not extract template name from URL: {original_url}")
            return jsonify({"error": "Invalid template URL in short URL"}), 400

        # Verify template exists
        try:
            templates = load_templates()
            template_names = [t['name'] for t in templates]
            if template_name not in template_names:
                logger.warning(f"Template '{template_name}' not found in available templates: {template_names}")
                return jsonify({"error": f"Template '{template_name}' not found"}), 404
        except Exception as e:
            logger.error(f"Failed to load templates for verification: {str(e)}")
            return jsonify({"error": "Failed to verify template existence due to database error"}), 500

        logger.debug(f"Rendering index page with pre-selected template: {template_name}")
        return index(preselected_template=template_name)
    except Exception as e:
        logger.error(f"Unexpected error in redirect_short_url for code {short_code}: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error during short URL redirect"}), 500

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
def index(preselected_template=None):
    logger.debug("Rendering index page with preselected_template: %s", preselected_template)
    # Initialize empty lists for profiles and config data
    ssl_ssh_profiles = []
    webfilter_profiles = []
    av_profiles = []
    application_lists = []
    ips_sensors = []
    interfaces = []
    addresses = []
    address_groups = []
    internet_services = []
    vips = []
    ip_pools = []
    services = []
    service_groups = {}
    users = []
    groups = []
    
    # Load profiles from the last parsed config (if available)
    config = load_last_config()
    if config:
        ssl_ssh_profiles = config.get('ssl_ssh_profiles', [])
        webfilter_profiles = config.get('webfilter_profiles', [])
        av_profiles = config.get('av_profiles', [])
        application_lists = config.get('application_lists', [])
        ips_sensors = config.get('ips_sensors', [])
        interfaces = config.get('interfaces', [])
        addresses = config.get('addresses', [])
        address_groups = config.get('address_groups', [])
        internet_services = config.get('internet_services', [])
        vips = config.get('vips', [])
        ip_pools = config.get('ip_pools', [])
        services = config.get('services', [])
        service_groups = config.get('service_groups', {})
        users = config.get('users', [])
        groups = config.get('groups', [])
        logger.debug("Loaded last config from SQLite")
    
    # Explicitly create context dictionary to ensure all variables are passed
    context = {
        'service_templates': SERVICE_TEMPLATES,
        'group_templates': SERVICE_GROUP_TEMPLATES,
        'ssl_ssh_profiles': ssl_ssh_profiles,
        'webfilter_profiles': webfilter_profiles,
        'av_profiles': av_profiles,
        'application_lists': application_lists,
        'ips_sensors': ips_sensors,
        'interfaces': interfaces,
        'addresses': addresses,
        'address_groups': address_groups,
        'internet_services': internet_services,
        'vips': vips,
        'ip_pools': ip_pools,
        'services': services,
        'service_groups': service_groups,
        'users': users,
        'groups': groups,
        'preselected_template': preselected_template,
        'templates': [t['name'] for t in load_templates()]
    }
    logger.debug("Template context: %s", context)
    return render_template('index.html', **context)

def save_template_to_db(template_name, template_data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO templates (name, data) VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET data = excluded.data
    ''', (template_name, json.dumps(template_data)))
    conn.commit()
    conn.close()
    logger.debug(f"Template '{template_name}' saved or updated in SQLite")

@app.route('/save_template', methods=['POST'])
def save_template():
    logger.debug("Received request to save template")
    data = request.form
    template_name = data.get('template_name')
    if not template_name:
        logger.error("No template name provided")
        return jsonify({"error": "Template name is required"}), 400

    policies = json.loads(data.get('policies', '[]')) or []
    if not policies:
        logger.error("No policies provided")
        return jsonify({"error": "At least one policy is required"}), 400

    template_data = {'policies': []}
    for policy in policies:
        policy_data = {
            'policy_id': policy.get('policy_id', str(uuid.uuid4())),
            'policy_name': policy.get('policy_name', ''),
            'policy_comment': policy.get('policy_comment', ''),
            'src_interfaces': policy.get('src_interfaces', []),
            'dst_interfaces': policy.get('dst_interfaces', []),
            'src_addresses': policy.get('src_addresses', []),
            'src_address_groups': policy.get('src_address_groups', []),
            'src_internet_services': policy.get('src_internet_services', []),
            'src_vips': policy.get('src_vips', []),
            'dst_addresses': policy.get('dst_addresses', []),
            'dst_address_groups': policy.get('dst_address_groups', []),
            'dst_internet_services': policy.get('dst_internet_services', []),
            'dst_vips': policy.get('dst_vips', []),
            'services': policy.get('services', []),
            'action': policy.get('action', ''),
            'inspection_mode': policy.get('inspection_mode', 'flow'),
            'ssl_ssh_profile': policy.get('ssl_ssh_profile', ''),
            'webfilter_profile': policy.get('webfilter_profile', ''),
            'webfilter_enabled': policy.get('webfilter_enabled', True),
            'av_profile': policy.get('av_profile', ''),
            'av_enabled': policy.get('av_enabled', False),
            'application_list': policy.get('application_list', ''),
            'application_list_enabled': policy.get('application_list_enabled', True),
            'ips_sensor': policy.get('ips_sensor', ''),
            'ips_sensor_enabled': policy.get('ips_sensor_enabled', True),
            'logtraffic': policy.get('logtraffic', ''),
            'logtraffic_start': policy.get('logtraffic_start', ''),
            'auto_asic_offload': policy.get('auto_asic_offload', ''),
            'nat': policy.get('nat', ''),
            'ip_pool': policy.get('ip_pool', ''),
            'users': policy.get('users', []),
            'groups': policy.get('groups', [])
        }
        if policy_data['action'].lower() == 'deny':
            policy_data['ssl_ssh_profile'] = ''
            policy_data['webfilter_enabled'] = False
            policy_data['webfilter_profile'] = ''
            policy_data['av_enabled'] = False
            policy_data['av_profile'] = ''
            policy_data['application_list_enabled'] = False
            policy_data['application_list'] = ''
            policy_data['ips_sensor_enabled'] = False
            policy_data['ips_sensor'] = ''
        logger.debug(f"Saving policy '{policy_data['policy_name']}': users={policy_data['users']}, groups={policy_data['groups']}, "
                     f"webfilter_enabled={policy_data['webfilter_enabled']}, application_list_enabled={policy_data['application_list_enabled']}, "
                     f"av_enabled={policy_data['av_enabled']}, ips_sensor_enabled={policy_data['ips_sensor_enabled']}, "
                     f"inspection_mode={policy_data['inspection_mode']}, ip_pool={policy_data['ip_pool']}")
        template_data['policies'].append(policy_data)

    try:
        save_template_to_db(template_name, template_data)
        return jsonify({"status": "success", "message": f"Template '{template_name}' saved"})
    except Exception as e:
        logger.error(f"Failed to save template '{template_name}': {str(e)}")
        return jsonify({"error": "Failed to save template"}), 500

@app.route('/import_template', methods=['POST'])
def import_template():
    logger.debug("Received request to import template")
    template_name = request.form.get('template_name')
    template_data_str = request.form.get('template_data')

    if not template_name:
        logger.error("Template name not provided")
        return jsonify({"error": "Template name is required"}), 400
    if not template_data_str:
        logger.error("Template data not provided")
        return jsonify({"error": "Template data is required"}), 400

    try:
        template_data = json.loads(template_data_str)
        if not isinstance(template_data, dict) or 'policies' not in template_data:
            logger.error("Invalid template data format")
            return jsonify({"error": "Invalid template data format: Must contain policies"}), 400

        required_policy_fields = [
            'policy_id', 'policy_name', 'policy_comment', 'src_interfaces', 'dst_interfaces',
            'src_addresses', 'src_address_groups', 'src_internet_services', 'src_vips',
            'dst_addresses', 'dst_address_groups', 'dst_internet_services', 'dst_vips',
            'services', 'action', 'inspection_mode', 'ssl_ssh_profile', 'webfilter_profile',
            'webfilter_enabled', 'av_profile', 'av_enabled', 'application_list',
            'application_list_enabled', 'ips_sensor', 'ips_sensor_enabled', 'logtraffic',
            'logtraffic_start', 'auto_asic_offload', 'nat', 'ip_pool', 'users', 'groups'
        ]
        for policy in template_data['policies']:
            for field in required_policy_fields:
                if field not in policy:
                    if field in ['webfilter_enabled', 'application_list_enabled', 'ips_sensor_enabled']:
                        policy[field] = True
                    elif field == 'av_enabled':
                        policy[field] = False
                    elif field == 'inspection_mode':
                        policy[field] = 'flow'
                    elif field in ['policy_name', 'policy_comment', 'action', 'ssl_ssh_profile',
                                   'webfilter_profile', 'av_profile', 'application_list', 'ips_sensor',
                                   'logtraffic', 'logtraffic_start', 'auto_asic_offload', 'nat', 'ip_pool']:
                        policy[field] = ''
                    else:
                        policy[field] = []
            policy['policy_id'] = str(uuid.uuid4())
            if policy['action'].lower() == 'deny':
                policy['ssl_ssh_profile'] = ''
                policy['webfilter_enabled'] = False
                policy['webfilter_profile'] = ''
                policy['av_enabled'] = False
                policy['av_profile'] = ''
                policy['application_list_enabled'] = False
                policy['application_list'] = ''
                policy['ips_sensor_enabled'] = False
                policy['ips_sensor'] = ''

        save_template_to_db(template_name, template_data)
        return jsonify({"status": "success", "message": f"Template '{template_name}' imported"})
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse template data: {str(e)}")
        return jsonify({"error": "Invalid JSON format"}), 400
    except Exception as e:
        logger.error(f"Failed to import template '{template_name}': {str(e)}")
        return jsonify({"error": "Failed to import template"}), 500

@app.route('/export_template/<template_name>', methods=['GET'])
def export_template(template_name):
    logger.debug(f"Received request to export template: {template_name}")
    templates = load_templates()
    for template in templates:
        if template['name'] == template_name:
            export_data = {
                'name': template_name,
                'data': template['data']
            }
            buffer = BytesIO()
            buffer.write(json.dumps(export_data, indent=2).encode('utf-8'))
            buffer.seek(0)
            logger.debug(f"Template '{template_name}' exported as JSON")
            return send_file(
                buffer,
                as_attachment=True,
                download_name=f"{template_name}.json",
                mimetype='application/json'
            )
    logger.error(f"Template '{template_name}' not found for export")
    return jsonify({"error": "Template not found"}), 404

@app.route('/load_templates', methods=['GET'])
def load_templates_endpoint():
    logger.debug("Received request to load templates")
    templates = load_templates()
    template_names = [t['name'] for t in templates]
    response = {"templates": template_names}
    logger.debug(f"Sending response: {json.dumps(response)}")
    return jsonify(response)

@app.route('/get_template/<template_name>', methods=['GET'])
def get_template(template_name):
    logger.debug(f"Received request to get template: {template_name}")
    templates = load_templates()
    for template in templates:
        if template['name'] == template_name:
            interfaces = set()
            addresses = set()
            address_groups = set()
            internet_services = set()
            vips = set()
            ip_pools = set()
            services = []
            service_groups = {}
            ssl_ssh_profiles = set()
            webfilter_profiles = set()
            av_profiles = set()
            application_lists = set()
            ips_sensors = set()
            users = set()
            groups = set()

            for policy in template['data']['policies']:
                interfaces.update(policy.get('src_interfaces', []))
                interfaces.update(policy.get('dst_interfaces', []))
                addresses.update(policy.get('src_addresses', []))
                addresses.update(policy.get('dst_addresses', []))
                address_groups.update(policy.get('src_address_groups', []))
                address_groups.update(policy.get('dst_address_groups', []))
                internet_services.update(policy.get('src_internet_services', []))
                internet_services.update(policy.get('dst_internet_services', []))
                vips.update(policy.get('src_vips', []))
                vips.update(policy.get('dst_vips', []))
                ip_pools.add(policy.get('ip_pool', '')) if policy.get('ip_pool') else None
                for svc in policy.get('services', []):
                    svc_type = svc.get('type', '')
                    svc_name = svc.get('name', '')
                    if svc_type == 'group' and svc_name not in service_groups:
                        service_groups[svc_name] = []
                    elif svc_type == 'template' or svc_type == 'custom':
                        svc_info = {
                            'name': svc_name,
                            'protocol': svc.get('protocol', 'TCP'),
                            'port': svc.get('port', '0')
                        }
                        if svc_type == 'template' and svc_name in KNOWN_SERVICES:
                            svc_info.update(KNOWN_SERVICES[svc_name])
                        if svc_info not in services:
                            services.append(svc_info)
                if policy.get('ssl_ssh_profile') and policy.get('action', '').lower() != 'deny':
                    ssl_ssh_profiles.add(policy['ssl_ssh_profile'])
                if policy.get('webfilter_profile') and policy.get('webfilter_enabled') and policy.get('action', '').lower() != 'deny':
                    webfilter_profiles.add(policy['webfilter_profile'])
                if policy.get('av_profile') and policy.get('av_enabled') and policy.get('action', '').lower() != 'deny':
                    av_profiles.add(policy['av_profile'])
                if policy.get('application_list') and policy.get('application_list_enabled') and policy.get('action', '').lower() != 'deny':
                    application_lists.add(policy['application_list'])
                if policy.get('ips_sensor') and policy.get('ips_sensor_enabled') and policy.get('action', '').lower() != 'deny':
                    ips_sensors.add(policy['ips_sensor'])
                users.update(policy.get('users', []))
                groups.update(policy.get('groups', []))

            logger.debug(f"Template '{template_name}' found")
            return jsonify({
                "status": "success",
                "data": template['data'],
                "config": {
                    "interfaces": list(interfaces),
                    "addresses": list(addresses),
                    "address_groups": list(address_groups),
                    "internet_services": list(internet_services),
                    "vips": list(vips),
                    "ip_pools": list(ip_pools),
                    "services": services,
                    "service_groups": service_groups,
                    "ssl_ssh_profiles": list(ssl_ssh_profiles),
                    "webfilter_profiles": list(webfilter_profiles),
                    "av_profiles": list(av_profiles),
                    "application_lists": list(application_lists),
                    "ips_sensors": list(ips_sensors),
                    "users": list(users),
                    "groups": list(groups)
                }
            })
    logger.error(f"Template '{template_name}' not found")
    return jsonify({"error": "Template not found"}), 404

@app.route('/delete_template/<template_name>', methods=['DELETE'])
def delete_template(template_name):
    logger.debug(f"Received request to delete template: {template_name}")
    templates = load_templates()
    original_length = len(templates)
    templates = [t for t in templates if t['name'] != template_name]
    
    short_urls = load_short_urls()
    template_url = f"{request.host_url}get_template/{template_name}"
    short_urls = {k: v for k, v in short_urls.items() if v != template_url}
    
    if len(templates) < original_length:
        save_templates(templates)
        save_short_urls(short_urls)
        logger.debug(f"Template '{template_name}' and its short URLs deleted")
        return jsonify({"status": "success", "message": f"Template '{template_name}' deleted"})
    logger.error(f"Template '{template_name}' not found")
    return jsonify({"error": "Template not found"}), 404

@app.route('/rename_template', methods=['POST'])
def rename_template():
    logger.debug("Received request to rename template")
    data = request.get_json()
    old_name = data.get('old_name')
    new_name = data.get('new_name')

    if not old_name:
        logger.error("Old template name not provided")
        return jsonify({"error": "Old template name is required"}), 400
    if not new_name:
        logger.error("New template name not provided")
        return jsonify({"error": "New template name is required"}), 400
    if old_name == new_name:
        logger.warning("Old and new template names are the same")
        return jsonify({"error": "New template name must be different from the old name"}), 400

    templates = load_templates()
    template_to_rename = None
    for template in templates:
        if template['name'] == old_name:
            template_to_rename = template
            break

    if not template_to_rename:
        logger.error(f"Template '{old_name}' not found for renaming")
        return jsonify({"error": "Template not found"}), 404

    for template in templates:
        if template['name'] == new_name:
            logger.error(f"Template '{new_name}' already exists")
            return jsonify({"error": "A template with the new name already exists"}), 400

    templates = [t for t in templates if t['name'] != old_name]
    template_to_rename['name'] = new_name
    templates.append(template_to_rename)

    short_urls = load_short_urls()
    old_url = f"{request.host_url}get_template/{old_name}"
    new_url = f"{request.host_url}get_template/{new_name}"
    for short_code, url in list(short_urls.items()):
        if url == old_url:
            short_urls[short_code] = new_url
            logger.debug(f"Updated short URL for {short_code}: {old_url} to {new_url}")

    try:
        save_templates(templates)
        save_short_urls(short_urls)
        logger.debug(f"Template renamed from '{old_name}' to '{new_name}'")
        return jsonify({"status": "success", "message": f"Template renamed to '{new_name}'"})
    except Exception as e:
        logger.error(f"Failed to rename template from '{old_name}' to '{new_name}': {str(e)}")
        return jsonify({"error": "Failed to rename template"}), 500

@app.route('/clone_template/<template_name>', methods=['POST'])
def clone_template(template_name):
    logger.debug(f"Received request to clone template: {template_name}")
    templates = load_templates()
    for template in templates:
        if template['name'] == template_name:
            new_template_name = f"{template_name}_clone_{uuid.uuid4().hex[:6]}"
            new_template_data = template['data'].copy()
            for policy in new_template_data['policies']:
                policy['policy_id'] = str(uuid.uuid4())
            save_template_to_db(new_template_name, new_template_data)
            logger.debug(f"Template '{template_name}' cloned as '{new_template_name}'")
            return jsonify({"status": "success", "new_template_name": new_template_name})
    logger.error(f"Template '{template_name}' not found for cloning")
    return jsonify({"error": "Template not found"}), 404

@app.route('/clone_policy', methods=['POST'])
def clone_policy():
    logger.debug("Received request to clone policy")
    data = request.get_json()
    policy_id = data.get('policy_id')
    templates = load_templates()
    
    for template in templates:
        for policy in template['data']['policies']:
            if policy['policy_id'] == policy_id:
                new_policy = policy.copy()
                new_policy['policy_id'] = str(uuid.uuid4())
                new_policy['policy_name'] = f"{policy['policy_name']}_clone_{uuid.uuid4().hex[:6]}"[:32]
                template['data']['policies'].append(new_policy)
                save_template_to_db(template['name'], template['data'])
                logger.debug(f"Policy '{policy_id}' cloned")
                return jsonify({"status": "success", "new_policy": new_policy})
    logger.error(f"Policy '{policy_id}' not found for cloning")
    return jsonify({"error": "Policy not found"}), 404

@app.route('/generate_policy', methods=['POST'])
def generate_policy():
    logger.debug("Received request to generate policy")
    data = request.form
    policies = json.loads(data.get('policies', '[]')) or []
    if not policies:
        logger.error("No policies provided")
        return jsonify({"error": "At least one policy is required"}), 400

    def generate_single_policy(policy_name, policy_comment, src_intfs, dst_intfs, src_addrs, src_agrps, src_isdbs, src_vips, dst_addrs, dst_agrps, dst_isdbs, dst_vips, svc_names, action, inspection_mode, ssl_ssh_profile, webfilter_profile, av_profile, application_list, ips_sensor, logtraffic, logtraffic_start, auto_asic_offload, nat, ip_pool, services, users, groups, include_custom_services=True):
        if not src_intfs or not dst_intfs or (not src_addrs and not src_agrps and not src_isdbs and not src_vips) or (not dst_addrs and not dst_agrps and not dst_isdbs and not dst_vips) or not svc_names:
            logger.warning(f"Skipping policy generation for {policy_name} due to missing required fields")
            return ""

        if len(policy_name) > 32:
            logger.debug(f"Policy name '{policy_name}' exceeds 32 characters; truncating to 32 characters")
            policy_name = policy_name[:32]

        cli_commands = "config firewall policy\n"
        cli_commands += "edit 0\n"
        cli_commands += f'set name "{policy_name}"\n'
        cli_commands += f'set comments "{policy_comment}"\n'
        cli_commands += "set srcintf " + " ".join([f'"{intf}"' for intf in src_intfs if intf]) + "\n"
        cli_commands += "set dstintf " + " ".join([f'"{intf}"' for intf in dst_intfs if intf]) + "\n"
        if src_addrs or src_agrps or src_vips:
            cli_commands += "set srcaddr " + " ".join([f'"{addr}"' for addr in (src_addrs + src_agrps + src_vips) if addr]) + "\n"
        if src_isdbs:
            cli_commands += "set internet-service-src enable\n"
            cli_commands += "set internet-service-id " + " ".join([f'"{isdb}"' for isdb in src_isdbs if isdb]) + "\n"
        if dst_addrs or dst_agrps or dst_vips:
            cli_commands += "set dstaddr " + " ".join([f'"{addr}"' for addr in (dst_addrs + dst_agrps + dst_vips) if addr]) + "\n"
        if dst_isdbs:
            cli_commands += "set internet-service enable\n"
            cli_commands += "set internet-service-id " + " ".join([f'"{isdb}"' for isdb in dst_isdbs if isdb]) + "\n"

        if users:
            cli_commands += "set users " + " ".join([f'"{user}"' for user in users if user]) + "\n"
        if groups:
            cli_commands += "set groups " + " ".join([f'"{group}"' for group in groups if group]) + "\n"

        if include_custom_services:
            for svc in services:
                if svc['type'] == 'custom' and f"custom_{svc['name']}" in svc_names:
                    svc_name = f"custom_{svc['name']}"
                    cli_commands += "config firewall service custom\n"
                    cli_commands += f'edit "{svc_name}"\n'
                    cli_commands += f"set {svc['protocol'].lower()} {svc['port']}\n"
                    cli_commands += "next\nend\n"

        cli_commands += "set service " + " ".join([f'"{svc}"' for svc in svc_names if svc]) + "\n"
        cli_commands += f'set action {action}\n'
        cli_commands += 'set schedule "always"\n'
        cli_commands += f'set inspection-mode {inspection_mode}\n'
        if action.lower() != 'deny' and (ssl_ssh_profile or (webfilter_profile and webfilter_profile != 'disable') or (av_profile and av_profile != 'disable') or (application_list and application_list != 'disable') or (ips_sensor and ips_sensor != 'disable')):
            cli_commands += 'set utm-status enable\n'
        if action.lower() != 'deny' and ssl_ssh_profile:
            cli_commands += f'set ssl-ssh-profile "{ssl_ssh_profile}"\n'
        if action.lower() != 'deny' and webfilter_profile and webfilter_profile != 'disable':
            cli_commands += f'set webfilter-profile "{webfilter_profile}"\n'
        if action.lower() != 'deny' and av_profile and av_profile != 'disable':
            cli_commands += f'set av-profile "{av_profile}"\n'
        if action.lower() != 'deny' and application_list and application_list != 'disable':
            cli_commands += f'set application-list "{application_list}"\n'
        if action.lower() != 'deny' and ips_sensor and ips_sensor != 'disable':
            cli_commands += f'set ips-sensor "{ips_sensor}"\n'
        cli_commands += f'set logtraffic {logtraffic}\n'
        cli_commands += f'set logtraffic-start {logtraffic_start}\n'
        cli_commands += f'set auto-asic-offload {auto_asic_offload}\n'
        cli_commands += f'set nat {nat}\n'
        if nat.lower() == 'enable' and ip_pool:
            cli_commands += f'set ippool enable\n'
            cli_commands += f'set poolname "{ip_pool}"\n'
        cli_commands += "next\nend\n"
        return cli_commands

    all_outputs = []
    for policy in policies:
        policy_name = policy.get('policy_name', 'policy')
        policy_comment = policy.get('policy_comment', 'policy')
        src_interfaces = policy.get('src_interfaces', [])
        dst_interfaces = policy.get('dst_interfaces', [])
        src_addresses = policy.get('src_addresses', [])
        src_address_groups = policy.get('src_address_groups', [])
        src_internet_services = policy.get('src_internet_services', [])
        src_vips = policy.get('src_vips', [])
        dst_addresses = policy.get('dst_addresses', [])
        dst_address_groups = policy.get('dst_address_groups', [])
        dst_internet_services = policy.get('dst_internet_services', [])
        dst_vips = policy.get('dst_vips', [])
        services = policy.get('services', [])
        action = policy.get('action', 'accept')
        inspection_mode = policy.get('inspection_mode', 'flow')
        ssl_ssh_profile = policy.get('ssl_ssh_profile', '') if action.lower() != 'deny' else ''
        webfilter_profile = policy.get('webfilter_profile', '') if policy.get('webfilter_enabled', False) and action.lower() != 'deny' else ''
        av_profile = policy.get('av_profile', '') if policy.get('av_enabled', False) and action.lower() != 'deny' else ''
        application_list = policy.get('application_list', '') if policy.get('application_list_enabled', False) and action.lower() != 'deny' else ''
        ips_sensor = policy.get('ips_sensor', '') if policy.get('ips_sensor_enabled', False) and action.lower() != 'deny' else ''
        logtraffic = policy.get('logtraffic', 'all')
        logtraffic_start = policy.get('logtraffic_start', 'enable')
        auto_asic_offload = policy.get('auto_asic_offload', 'enable')
        nat = policy.get('nat', 'enable')
        ip_pool = policy.get('ip_pool', '')
        users = policy.get('users', [])
        groups = policy.get('groups', [])

        logger.debug(f"Generating policy: {policy_name}")
        logger.debug(f"Policy Comment: {policy_comment}")
        logger.debug(f"Source Interfaces: {src_interfaces}")
        logger.debug(f"Destination Interfaces: {dst_interfaces}")
        logger.debug(f"Source Addresses: {src_addresses}")
        logger.debug(f"Source Address Groups: {src_address_groups}")
        logger.debug(f"Source Internet Services: {src_internet_services}")
        logger.debug(f"Source VIPs: {src_vips}")
        logger.debug(f"Destination Addresses: {dst_addresses}")
        logger.debug(f"Destination Address Groups: {dst_address_groups}")
        logger.debug(f"Destination Internet Services: {dst_internet_services}")
        logger.debug(f"Destination VIPs: {dst_vips}")
        logger.debug(f"Services: {services}")
        logger.debug(f"Action: {action}")
        logger.debug(f"Inspection Mode: {inspection_mode}")
        logger.debug(f"SSL/SSH Profile: {ssl_ssh_profile}")
        logger.debug(f"Webfilter Profile: {webfilter_profile}")
        logger.debug(f"Antivirus Profile: {av_profile}")
        logger.debug(f"Application List: {application_list}")
        logger.debug(f"IPS Sensor: {ips_sensor}")
        logger.debug(f"Log Traffic: {logtraffic}")
        logger.debug(f"Log Traffic Start: {logtraffic_start}")
        logger.debug(f"Auto ASIC Offload: {auto_asic_offload}")
        logger.debug(f"NAT: {nat}")
        logger.debug(f"IP Pool: {ip_pool}")
        logger.debug(f"Users: {users}")
        logger.debug(f"Groups: {groups}")

        service_names = []
        for svc in services:
            if svc['type'] == 'group':
                service_names.append(svc['name'])
            elif svc['type'] == 'template':
                service_names.append(svc['name'])
            elif svc['type'] == 'custom':
                svc_name = f"custom_{svc['name']}"
                service_names.append(svc_name)

        output1 = generate_single_policy(
            policy_name=policy_name,
            policy_comment=policy_comment,
            src_intfs=src_interfaces,
            dst_intfs=dst_interfaces,
            src_addrs=src_addresses,
            src_agrps=src_address_groups,
            src_isdbs=src_internet_services,
            src_vips=src_vips,
            dst_addrs=dst_addresses,
            dst_agrps=dst_address_groups,
            dst_isdbs=dst_internet_services,
            dst_vips=dst_vips,
            svc_names=service_names,
            action=action,
            inspection_mode=inspection_mode,
            ssl_ssh_profile=ssl_ssh_profile,
            webfilter_profile=webfilter_profile,
            av_profile=av_profile,
            application_list=application_list,
            ips_sensor=ips_sensor,
            logtraffic=logtraffic,
            logtraffic_start=logtraffic_start,
            auto_asic_offload=auto_asic_offload,
            nat=nat,
            ip_pool=ip_pool,
            services=services,
            users=users,
            groups=groups
        )
        logger.debug("Output 1 (All in one policy):\n%s", output1)

        output2 = ""
        if service_names:
            for svc in service_names:
                policy_name_svc = f"{policy_name}-{svc}"[:32]
                output2 += generate_single_policy(
                    policy_name=policy_name_svc,
                    policy_comment=policy_comment,
                    src_intfs=src_interfaces,
                    dst_intfs=dst_interfaces,
                    src_addrs=src_addresses,
                    src_agrps=src_address_groups,
                    src_isdbs=src_internet_services,
                    src_vips=src_vips,
                    dst_addrs=dst_addresses,
                    dst_agrps=dst_address_groups,
                    dst_isdbs=dst_internet_services,
                    dst_vips=dst_vips,
                    svc_names=[svc],
                    action=action,
                    inspection_mode=inspection_mode,
                    ssl_ssh_profile=ssl_ssh_profile,
                    webfilter_profile=webfilter_profile,
                    av_profile=av_profile,
                    application_list=application_list,
                    ips_sensor=ips_sensor,
                    logtraffic=logtraffic,
                    logtraffic_start=logtraffic_start,
                    auto_asic_offload=auto_asic_offload,
                    nat=nat,
                    ip_pool=ip_pool,
                    services=services,
                    users=users,
                    groups=groups
                )
                output2 += "\n" if output2 else ""
        else:
            output2 = "No services defined for this policy."
        logger.debug("Output 2 (One policy per service):\n%s", output2)

        output3 = ""
        if src_interfaces and dst_interfaces and service_names:
            for src_intf in src_interfaces:
                if not src_intf:
                    continue
                for dst_intf in dst_interfaces:
                    if not dst_intf:
                        continue
                    for svc in service_names:
                        if not svc:
                            continue
                        policy_name_intf_svc = f"{policy_name}-{src_intf}-{dst_intf}-{svc}"[:32]
                        output3 += generate_single_policy(
                            policy_name=policy_name_intf_svc,
                            policy_comment=policy_comment,
                            src_intfs=[src_intf],
                            dst_intfs=[dst_intf],
                            src_addrs=src_addresses,
                            src_agrps=src_address_groups,
                            src_isdbs=src_internet_services,
                            src_vips=src_vips,
                            dst_addrs=dst_addresses,
                            dst_agrps=dst_address_groups,
                            dst_isdbs=dst_internet_services,
                            dst_vips=dst_vips,
                            svc_names=[svc],
                            action=action,
                            inspection_mode=inspection_mode,
                            ssl_ssh_profile=ssl_ssh_profile,
                            webfilter_profile=webfilter_profile,
                            av_profile=av_profile,
                            application_list=application_list,
                            ips_sensor=ips_sensor,
                            logtraffic=logtraffic,
                            logtraffic_start=logtraffic_start,
                            auto_asic_offload=auto_asic_offload,
                            nat=nat,
                            ip_pool=ip_pool,
                            services=services,
                            users=users,
                            groups=groups
                        )
                        output3 += "\n" if output3 else ""
        else:
            output3 = "No valid source interfaces, destination interfaces, or services defined for this policy."
        logger.debug("Output 3 (One policy per src interface, dst interface, and service):\n%s", output3)

        all_outputs.append({
            "policy_id": policy.get('policy_id', str(uuid.uuid4())),
            "policy_name": policy_name,
            "output1": output1 if output1 else "No policy generated due to missing fields.",
            "output2": output2 if output2 else "No policy generated due to missing services.",
            "output3": output3 if output3 else "No policy generated due to missing interfaces or services."
        })

    response = {"outputs": all_outputs}
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

    interfaces = []
    addresses = []
    address_groups = []
    internet_services = []
    vips = []
    ip_pools = []
    services = []
    service_groups = {}
    ssl_ssh_profiles = []
    webfilter_profiles = []
    av_profiles = []
    application_lists = []
    ips_sensors = []
    users = []
    groups = []

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

    address_pattern = re.compile(r'config firewall address\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in address_pattern.finditer(content):
        address_name = match.group(1)
        addresses.append(address_name)
        logger.debug("Found address: %s", address_name)

    addrgrp_pattern = re.compile(r'config firewall addrgrp\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in addrgrp_pattern.finditer(content):
        addrgrp_name = match.group(1)
        if addrgrp_name not in addresses:
            addresses.append(addrgrp_name)
            address_groups.append(addrgrp_name)
            logger.debug("Found address group: %s", addrgrp_name)

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
                        if inside_addrgrp_section:
                            address_groups.append(address_name)
                        logger.debug("Found %s (fallback): %s", "address group" if inside_addrgrp_section else "address", address_name)

    policy_addr_pattern = re.compile(r'set (?:srcaddr|dstaddr)\s+((?:"[^"]+"\s*)+)', re.DOTALL)
    for match in policy_addr_pattern.finditer(content):
        addr_list = [addr.strip('"') for addr in match.group(1).split()]
        for addr in addr_list:
            if addr not in addresses:
                addresses.append(addr)
                logger.debug("Found address from policy: %s", addr)

    internet_service_pattern = re.compile(r'config firewall internet-service-name\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in internet_service_pattern.finditer(content):
        isdb_name = match.group(1)
        internet_services.append(isdb_name)
        logger.debug("Found internet service: %s", isdb_name)

    policy_isdb_pattern = re.compile(r'set internet-service-id\s+((?:"[^"]+"\s*)+)', re.DOTALL)
    for match in policy_isdb_pattern.finditer(content):
        isdb_list = [isdb.strip('"') for isdb in match.group(1).split()]
        for isdb in isdb_list:
            if isdb not in internet_services:
                internet_services.append(isdb)
                logger.debug("Found internet service from policy: %s", isdb)

    vip_pattern = re.compile(r'config firewall vip\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in vip_pattern.finditer(content):
        vip_name = match.group(1)
        vips.append(vip_name)
        addresses.append(vip_name)
        logger.debug("Found virtual IP: %s", vip_name)

    policy_vip_pattern = re.compile(r'set (?:srcaddr|dstaddr)\s+((?:"[^"]+"\s*)+)', re.DOTALL)
    for match in policy_vip_pattern.finditer(content):
        vip_list = [vip.strip('"') for vip in match.group(1).split()]
        for vip in vip_list:
            if vip not in vips and vip in addresses:
                vips.append(vip)
                logger.debug("Found virtual IP from policy: %s", vip)

    ip_pool_pattern = re.compile(r'config firewall ippool\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in ip_pool_pattern.finditer(content):
        pool_name = match.group(1)
        ip_pools.append(pool_name)
        logger.debug("Found IP pool: %s", pool_name)

    policy_ip_pool_pattern = re.compile(r'set poolname\s+((?:"[^"]+"\s*)+)', re.DOTALL)
    for match in policy_ip_pool_pattern.finditer(content):
        pool_list = [pool.strip('"') for pool in match.group(1).split()]
        for pool in pool_list:
            if pool not in ip_pools:
                ip_pools.append(pool)
                logger.debug("Found IP pool from policy: %s", pool)

    service_pattern = re.compile(
        r'config firewall service custom\s+edit\s+"([^"]+)"\s+((?:set\s+[^\n]+\n)*)\s+next',
        re.DOTALL
    )
    for match in service_pattern.finditer(content):
        service_name = match.group(1)
        service_config = match.group(2)
        protocol = 'TCP'
        port = '0'

        protocol_match = re.search(r'set\s+(\w+)\s+([^\n]+)', service_config)
        if protocol_match:
            protocol = protocol_match.group(1).upper()
            port = protocol_match.group(2).strip()
        else:
            if 'tcp' in service_config.lower():
                protocol = 'TCP'
            elif 'udp' in service_config.lower():
                protocol = 'UDP'
            port_match = re.search(r'\b\d+\b', service_config)
            if port_match:
                port = port_match.group(0)

        services.append({"name": service_name, "protocol": protocol, "port": port})
        logger.debug("Found service: %s (protocol: %s, port: %s)", service_name, protocol, port)

    policy_service_pattern = re.compile(r'set service\s+((?:"[^"]+"\s*)+)', re.DOTALL)
    for match in policy_service_pattern.finditer(content):
        svc_list = [svc.strip('"') for svc in match.group(1).split()]
        for svc in svc_list:
            if svc not in [s['name'] for s in services] and svc not in service_groups:
                svc_info = KNOWN_SERVICES.get(svc, {"protocol": "TCP", "port": "0"})
                services.append({"name": svc, "protocol": svc_info["protocol"], "port": svc_info["port"]})
                logger.debug("Found service from policy: %s (protocol: %s, port: %s)", svc, svc_info["protocol"], svc_info["port"])

    service_group_pattern = re.compile(r'config firewall service group\s+edit\s+"([^"]+)"\s+set member\s+([^\n]+)\s+next', re.DOTALL)
    for match in service_group_pattern.finditer(content):
        group_name = match.group(1)
        members = [m.strip('"') for m in match.group(2).split()]
        service_groups[group_name] = members
        logger.debug("Found service group: %s with members: %s", group_name, members)

    user_pattern = re.compile(r'config user local\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in user_pattern.finditer(content):
        user_name = match.group(1)
        if user_name not in users:
            users.append(user_name)
            logger.debug("Found user: %s", user_name)

    group_pattern = re.compile(r'config user group\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in group_pattern.finditer(content):
        group_name = match.group(1)
        if group_name not in groups:
            groups.append(group_name)
            logger.debug("Found user group: %s", group_name)

    ssl_ssh_pattern = re.compile(r'config firewall ssl-ssh-profile\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in ssl_ssh_pattern.finditer(content):
        profile_name = match.group(1)
        if profile_name not in ssl_ssh_profiles:
            ssl_ssh_profiles.append(profile_name)
            logger.debug("Found SSL/SSH profile: %s", profile_name)
    logger.debug("Total SSL/SSH profiles found via regex: %d", len(ssl_ssh_profiles))

    webfilter_pattern = re.compile(r'config webfilter profile\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in webfilter_pattern.finditer(content):
        profile_name = match.group(1)
        if profile_name not in webfilter_profiles:
            webfilter_profiles.append(profile_name)
            logger.debug("Found webfilter profile: %s", profile_name)
    logger.debug("Total webfilter profiles found via regex: %d", len(webfilter_profiles))

    av_pattern = re.compile(r'config antivirus profile\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in av_pattern.finditer(content):
        profile_name = match.group(1)
        if profile_name not in av_profiles:
            av_profiles.append(profile_name)
            logger.debug("Found antivirus profile: %s", profile_name)
    logger.debug("Total antivirus profiles found via regex: %d", len(av_profiles))

    application_pattern = re.compile(r'config application list\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in application_pattern.finditer(content):
        list_name = match.group(1)
        if list_name not in application_lists:
            application_lists.append(list_name)
            logger.debug("Found application list: %s", list_name)
    logger.debug("Total application lists found via regex: %d", len(application_lists))

    ips_pattern = re.compile(r'config ips sensor\s+edit\s+"([^"]+)"\s*(?:.*?\n)*(?=\s*(?:edit\s+"[^"]+"|end))', re.DOTALL)
    for match in ips_pattern.finditer(content):
        sensor_name = match.group(1)
        if sensor_name not in ips_sensors:
            ips_sensors.append(sensor_name)
            logger.debug("Found IPS sensor: %s", sensor_name)
    logger.debug("Total IPS sensors found via regex: %d", len(ips_sensors))

    lines = content.splitlines()
    inside_interface_section = False
    inside_address_section = False
    inside_addrgrp_section = False
    inside_internet_service_section = False
    inside_vip_section = False
    inside_ip_pool_section = False
    inside_service_section = False
    inside_service_group_section = False
    inside_user_section = False
    inside_group_section = False
    inside_ssl_ssh_section = False
    inside_webfilter_section = False
    inside_av_section = False
    inside_application_section = False
    inside_ips_section = False
    nested_level = 0
    for i, line in enumerate(lines):
        line = line.strip()
        logger.debug("Processing line %d: %s", i, line)
        if line.startswith('config system interface'):
            inside_interface_section = True
            logger.debug("Entered config system interface section")
            continue
        if line.startswith('config firewall address'):
            inside_address_section = True
            logger.debug("Entered config firewall address section")
            continue
        if line.startswith('config firewall addrgrp'):
            inside_addrgrp_section = True
            logger.debug("Entered config firewall addrgrp section")
            continue
        if line.startswith('config firewall internet-service-name'):
            inside_internet_service_section = True
            logger.debug("Entered config firewall internet-service-name section")
            continue
        if line.startswith('config firewall vip'):
            inside_vip_section = True
            logger.debug("Entered config firewall vip section")
            continue
        if line.startswith('config firewall ippool'):
            inside_ip_pool_section = True
            logger.debug("Entered config firewall ippool section")
            continue
        if line.startswith('config firewall service custom'):
            inside_service_section = True
            logger.debug("Entered config firewall service custom section")
            continue
        if line.startswith('config firewall service group'):
            inside_service_group_section = True
            logger.debug("Entered config firewall service group section")
            continue
        if line.startswith('config user local'):
            inside_user_section = True
            logger.debug("Entered config user local section")
            continue
        if line.startswith('config user group'):
            inside_group_section = True
            logger.debug("Entered config user group section")
            continue
        if line.startswith('config firewall ssl-ssh-profile'):
            inside_ssl_ssh_section = True
            logger.debug("Entered config firewall ssl-ssh-profile section")
            continue
        if line.startswith('config webfilter profile'):
            inside_webfilter_section = True
            nested_level = 0
            logger.debug("Entered config webfilter profile section")
            continue
        if line.startswith('config antivirus profile'):
            inside_av_section = True
            nested_level = 0
            logger.debug("Entered config antivirus profile section")
            continue
        if line.startswith('config application list'):
            inside_application_section = True
            logger.debug("Entered config application list section")
            continue
        if line.startswith('config ips sensor'):
            inside_ips_section = True
            logger.debug("Entered config ips sensor section")
            continue
        if line.startswith('config '):
            nested_level += 1
            logger.debug("Entered nested config section, level: %d", nested_level)
            continue
        if line.startswith('end'):
            if nested_level > 0:
                nested_level -= 1
                logger.debug("Exited nested config section, level: %d", nested_level)
            elif inside_interface_section:
                inside_interface_section = False
                logger.debug("Exited config system interface section")
            elif inside_address_section:
                inside_address_section = False
                logger.debug("Exited config firewall address section")
            elif inside_addrgrp_section:
                inside_addrgrp_section = False
                logger.debug("Exited config firewall addrgrp section")
            elif inside_internet_service_section:
                inside_internet_service_section = False
                logger.debug("Exited config firewall internet-service-name section")
            elif inside_vip_section:
                inside_vip_section = False
                logger.debug("Exited config firewall vip section")
            elif inside_ip_pool_section:
                inside_ip_pool_section = False
                logger.debug("Exited config firewall ippool section")
            elif inside_service_section:
                inside_service_section = False
                logger.debug("Exited config firewall service custom section")
            elif inside_service_group_section:
                inside_service_group_section = False
                logger.debug("Exited config firewall service group section")
            elif inside_user_section:
                inside_user_section = False
                logger.debug("Exited config user local section")
            elif inside_group_section:
                inside_group_section = False
                logger.debug("Exited config user group section")
            elif inside_ssl_ssh_section:
                inside_ssl_ssh_section = False
                logger.debug("Exited config firewall ssl-ssh-profile section")
            elif inside_webfilter_section:
                inside_webfilter_section = False
                logger.debug("Exited config webfilter profile section")
            elif inside_av_section:
                inside_av_section = False
                logger.debug("Exited config antivirus profile section")
            elif inside_application_section:
                inside_application_section = False
                logger.debug("Exited config application list section")
            elif inside_ips_section:
                inside_ips_section = False
                logger.debug("Exited config ips sensor section")
            continue
        if line.startswith('edit ') and (
            inside_interface_section or
            inside_address_section or
            inside_addrgrp_section or
            inside_internet_service_section or
            inside_vip_section or
            inside_ip_pool_section or
            inside_service_section or
            inside_service_group_section or
            inside_user_section or
            inside_group_section or
            inside_ssl_ssh_section or
            inside_webfilter_section or
            inside_av_section or
            inside_application_section or
            inside_ips_section
        ):
            logger.debug("Processing edit line: %s", line)
            match = re.match(r'edit\s+"([^"]+)"', line)
            if match:
                name = match.group(1)
                if inside_interface_section and name not in interfaces:
                    interfaces.append(name)
                    logger.debug("Found interface (fallback): %s", name)
                elif inside_address_section and name not in addresses:
                    addresses.append(name)
                    logger.debug("Found address (fallback): %s", name)
                elif inside_addrgrp_section and name not in addresses:
                    addresses.append(name)
                    address_groups.append(name)
                    logger.debug("Found address group (fallback): %s", name)
                elif inside_internet_service_section and name not in internet_services:
                    internet_services.append(name)
                    logger.debug("Found internet service (fallback): %s", name)
                elif inside_vip_section and name not in vips:
                    vips.append(name)
                    addresses.append(name)
                    logger.debug("Found virtual IP (fallback): %s", name)
                elif inside_ip_pool_section and name not in ip_pools:
                    ip_pools.append(name)
                    logger.debug("Found IP pool (fallback): %s", name)
                elif inside_user_section and name not in users:
                    users.append(name)
                    logger.debug("Found user (fallback): %s", name)
                elif inside_group_section and name not in groups:
                    groups.append(name)
                    logger.debug("Found user group (fallback): %s", name)
                elif inside_ssl_ssh_section and name not in ssl_ssh_profiles:
                    ssl_ssh_profiles.append(name)
                    logger.debug("Found SSL/SSH profile (fallback): %s", name)
                elif inside_webfilter_section and name not in webfilter_profiles:
                    webfilter_profiles.append(name)
                    logger.debug("Found webfilter profile (fallback): %s", name)
                elif inside_av_section and name not in av_profiles:
                    av_profiles.append(name)
                    logger.debug("Found antivirus profile (fallback): %s", name)
                elif inside_application_section and name not in application_lists:
                    application_lists.append(name)
                    logger.debug("Found application list (fallback): %s", name)
                elif inside_ips_section and name not in ips_sensors:
                    ips_sensors.append(name)
                    logger.debug("Found IPS sensor (fallback): %s", name)
            else:
                logger.debug("Edit line did not match regex: %s", line)

    logger.debug("Final total interfaces found: %d", len(interfaces))
    logger.debug("Final total addresses found: %d", len(addresses))
    logger.debug("Final total address groups found: %d", len(address_groups))
    logger.debug("Final total internet services found: %d", len(internet_services))
    logger.debug("Final total virtual IPs found: %d", len(vips))
    logger.debug("Final total IP pools found: %d", len(ip_pools))
    logger.debug("Final total services found: %d", len(services))
    logger.debug("Final total service groups found: %d", len(service_groups))
    logger.debug("Final total users found: %d", len(users))
    logger.debug("Final total user groups found: %d", len(groups))
    logger.debug("Final total SSL/SSH profiles found: %d", len(ssl_ssh_profiles))
    logger.debug("Final total webfilter profiles found: %d", len(webfilter_profiles))
    logger.debug("Final total antivirus profiles found: %d", len(av_profiles))
    logger.debug("Final total application lists found: %d", len(application_lists))
    logger.debug("Final total IPS sensors found: %d", len(ips_sensors))

    response = {
        "interfaces": interfaces,
        "addresses": addresses,
        "address_groups": address_groups,
        "internet_services": internet_services,
        "vips": vips,
        "ip_pools": ip_pools,
        "services": services,
        "service_groups": service_groups,
        "ssl_ssh_profiles": ssl_ssh_profiles,
        "webfilter_profiles": webfilter_profiles,
        "av_profiles": av_profiles,
        "application_lists": application_lists,
        "ips_sensors": ips_sensors,
        "users": users,
        "groups": groups
    }
    
    save_last_config(response)
    
    logger.debug("Returning parsed config response: %s", response)
    return jsonify(response)

if __name__ == '__main__':
    logger.info("Starting Flask application on host 0.0.0.0, port 5000")
    app.run(host='0.0.0.0', port=5000, debug=False)