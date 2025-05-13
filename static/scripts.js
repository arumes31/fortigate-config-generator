let policies = [];
let interfaces = [];
let addresses = [];
let services = [];
let serviceGroups = {};
let sslSshProfiles = [];
let webfilterProfiles = [];
let applicationLists = [];
let ipsSensors = [];

function addPolicy() {
    const policyId = Date.now().toString();
    policies.push({
        id: policyId,
        name: '',
        comment: '',
        srcInterfaces: [],
        dstInterfaces: [],
        srcAddresses: [],
        dstAddresses: [],
        services: [],
        action: 'accept',
        ssl_ssh_profile: '',
        webfilter_profile: '',
        application_list: '',
        ips_sensor: '',
        logtraffic: 'all',
        logtraffic_start: 'enable',
        auto_asic_offload: 'enable',
        nat: 'disable'
    });
    renderPolicyList();
    selectPolicy(policyId);
}

function renderPolicyList() {
    const policyList = document.getElementById('policy-list');
    if (!policyList) {
        console.error('Policy list element not found');
        return;
    }
    policyList.innerHTML = '';
    policies.forEach(policy => {
        const div = document.createElement('div');
        div.className = 'policy-item';
        div.innerHTML = `
            <span onclick="selectPolicy('${policy.id}')">${policy.name || 'Unnamed Policy'}</span>
            <button class="clone-btn" onclick="clonePolicy(this)" data-policy-id="${policy.id}" aria-label="Clone policy">➕</button>
            <button class="delete-btn" onclick="deletePolicy('${policy.id}')" aria-label="Delete policy">🗑️</button>
        `;
        policyList.appendChild(div);
    });
}

function selectPolicy(policyId) {
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }

    const form = document.getElementById('policy-form');
    if (!form) {
        console.error('Policy form element not found');
        return;
    }
    form.dataset.policyId = policyId;

    try {
        form.querySelector('.policy-name').value = policy.name || '';
        form.querySelector('.policy-comment').value = policy.comment || '';
        form.querySelector('.action').value = policy.action || 'accept';
        form.querySelector('.ssl-ssh-profile').value = policy.ssl_ssh_profile || '';
        form.querySelector('.webfilter-profile').value = policy.webfilter_profile || '';
        form.querySelector('.application-list').value = policy.application_list || '';
        form.querySelector('.ips-sensor').value = policy.ips_sensor || '';
        form.querySelector('.logtraffic').value = policy.logtraffic || 'all';
        form.querySelector('.logtraffic-start').value = policy.logtraffic_start || 'enable';
        form.querySelector('.auto-asic-offload').value = policy.auto_asic_offload || 'enable';
        form.querySelector('.nat').value = policy.nat || 'disable';

        renderInterfaces(form.querySelector('.src-interfaces'), policy.srcInterfaces, 'src');
        renderInterfaces(form.querySelector('.dst-interfaces'), policy.dstInterfaces, 'dst');
        renderAddresses(form.querySelector('.src-addresses'), policy.srcAddresses, 'src');
        renderAddresses(form.querySelector('.dst-addresses'), policy.dstAddresses, 'dst');
        renderServices(form.querySelector('.services'), policy.services);
    } catch (error) {
        console.error('Error in selectPolicy:', error);
    }
}

function renderInterfaces(container, items, type) {
    if (!container) {
        console.error('Interface container not found');
        return;
    }
    container.innerHTML = '';
    items.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = 'interface-item';
        div.innerHTML = `
            <select onchange="updateInterface('${type}', ${index}, this.value)">
                <option value="">Select Interface</option>
                ${interfaces.map(intf => `<option value="${intf}" ${item === intf ? 'selected' : ''}>${intf}</option>`).join('')}
            </select>
            <button onclick="deleteInterface('${type}', ${index})">Delete</button>
        `;
        container.appendChild(div);
    });
}

function renderAddresses(container, items, type) {
    if (!container) {
        console.error('Address container not found');
        return;
    }
    container.innerHTML = '';
    items.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = 'address-item';
        div.innerHTML = `
            <select onchange="updateAddress('${type}', ${index}, this.value)">
                <option value="">Select Address</option>
                ${addresses.map(addr => `<option value="${addr}" ${item === addr ? 'selected' : ''}>${addr}</option>`).join('')}
            </select>
            <button onclick="deleteAddress('${type}', ${index})">Delete</button>
        `;
        container.appendChild(div);
    });
}

function renderServices(container, items) {
    if (!container) {
        console.error('Service container not found');
        return;
    }
    container.innerHTML = '';
    items.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = 'service-item';
        div.innerHTML = `
            <select onchange="updateService(${index}, this.value)">
                <option value="">Select Service/Group</option>
                <optgroup label="Service Groups">
                    ${Object.keys(serviceGroups).map(group => `<option value="group:${group}" ${item.type === 'group' && item.name === group ? 'selected' : ''}>${group}</option>`).join('')}
                </optgroup>
                <optgroup label="Individual Services">
                    ${services.map(svc => `<option value="template:${svc.name}" ${item.type === 'template' && item.name === svc.name ? 'selected' : ''}>${svc.name}</option>`).join('')}
                </optgroup>
                <optgroup label="Custom">
                    <option value="custom" ${item.type === 'custom' ? 'selected' : ''}>Custom</option>
                </optgroup>
            </select>
            ${item.type === 'custom' ? `
                <input type="text" value="${item.name}" onchange="updateCustomService(${index}, 'name', this.value)" placeholder="Service Name">
                <select onchange="updateCustomService(${index}, 'protocol', this.value)">
                    <option value="TCP" ${item.protocol === 'TCP' ? 'selected' : ''}>TCP</option>
                    <option value="UDP" ${item.protocol === 'UDP' ? 'selected' : ''}>UDP</option>
                    <option value="ICMP" ${item.protocol === 'ICMP' ? 'selected' : ''}>ICMP</option>
                </select>
                <input type="text" value="${item.port}" onchange="updateCustomService(${index}, 'port', this.value)" placeholder="Port">
            ` : ''}
            <button onclick="deleteService(${index})">Delete</button>
        `;
        container.appendChild(div);
    });
}

function updateDropdowns() {
    const form = document.getElementById('policy-form');
    if (!form) {
        console.error('Policy form not found for updating dropdowns');
        return;
    }
    const sslSshSelect = form.querySelector('.ssl-ssh-profile');
    const webfilterSelect = form.querySelector('.webfilter-profile');
    const appListSelect = form.querySelector('.application-list');
    const ipsSensorSelect = form.querySelector('.ips-sensor');

    if (!sslSshSelect || !webfilterSelect || !appListSelect || !ipsSensorSelect) {
        console.error('One or more dropdown elements not found');
        return;
    }

    sslSshSelect.innerHTML = `<option value="">None</option>${sslSshProfiles.map(p => `<option value="${p}">${p}</option>`).join('')}`;
    webfilterSelect.innerHTML = `<option value="">None</option>${webfilterProfiles.map(p => `<option value="${p}">${p}</option>`).join('')}`;
    appListSelect.innerHTML = `<option value="">None</option>${applicationLists.map(l => `<option value="${l}">${l}</option>`).join('')}`;
    ipsSensorSelect.innerHTML = `<option value="">None</option>${ipsSensors.map(s => `<option value="${s}">${s}</option>`).join('')}`;

    const policyId = form.dataset.policyId;
    if (policyId) {
        selectPolicy(policyId);
    }
}

function addSrcInterface(button) {
    const policyId = button.closest('#policy-form')?.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for adding source interface');
        return;
    }
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }
    policy.srcInterfaces.push('');
    selectPolicy(policyId);
}

function addDstInterface(button) {
    const policyId = button.closest('#policy-form')?.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for adding destination interface');
        return;
    }
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }
    policy.dstInterfaces.push('');
    selectPolicy(policyId);
}

function addSrcAddress(button) {
    const policyId = button.closest('#policy-form')?.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for adding source address');
        return;
    }
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }
    policy.srcAddresses.push('');
    selectPolicy(policyId);
}

function addDstAddress(button) {
    const policyId = button.closest('#policy-form')?.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for adding destination address');
        return;
    }
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }
    policy.dstAddresses.push('');
    selectPolicy(policyId);
}

function addService(button) {
    const policyId = button.closest('#policy-form')?.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for adding service');
        return;
    }
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }
    policy.services.push({ type: '', name: '', protocol: 'TCP', port: '' });
    selectPolicy(policyId);
}

function updateInterface(type, index, value) {
    const policyId = document.getElementById('policy-form')?.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for updating interface');
        return;
    }
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }
    if (type === 'src') {
        policy.srcInterfaces[index] = value;
    } else {
        policy.dstInterfaces[index] = value;
    }
}

function updateAddress(type, index, value) {
    const policyId = document.getElementById('policy-form')?.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for updating address');
        return;
    }
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }
    if (type === 'src') {
        policy.srcAddresses[index] = value;
    } else {
        policy.dstAddresses[index] = value;
    }
}

function updateService(index, value) {
    const policyId = document.getElementById('policy-form')?.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for updating service');
        return;
    }
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }
    const [type, name] = value.split(':');
    if (type === 'custom') {
        policy.services[index] = { type: 'custom', name: '', protocol: 'TCP', port: '' };
    } else if (type === 'group') {
        policy.services[index] = { type: 'group', name: name };
    } else {
        policy.services[index] = { type: 'template', name: name };
    }
    selectPolicy(policyId);
}

function updateCustomService(index, field, value) {
    const policyId = document.getElementById('policy-form')?.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for updating custom service');
        return;
    }
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }
    policy.services[index][field] = value;
}

function deleteInterface(type, index) {
    const policyId = document.getElementById('policy-form')?.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for deleting interface');
        return;
    }
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }
    if (type === 'src') {
        policy.srcInterfaces.splice(index, 1);
    } else {
        policy.dstInterfaces.splice(index, 1);
    }
    selectPolicy(policyId);
}

function deleteAddress(type, index) {
    const policyId = document.getElementById('policy-form')?.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for deleting address');
        return;
    }
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }
    if (type === 'src') {
        policy.srcAddresses.splice(index, 1);
    } else {
        policy.dstAddresses.splice(index, 1);
    }
    selectPolicy(policyId);
}

function deleteService(index) {
    const policyId = document.getElementById('policy-form')?.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for deleting service');
        return;
    }
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }
    policy.services.splice(index, 1);
    selectPolicy(policyId);
}

function deletePolicy(policyId) {
    policies = policies.filter(p => p.id !== policyId);
    renderPolicyList();
    if (policies.length > 0) {
        selectPolicy(policies[0].id);
    } else {
        clearForm();
    }
}

function savePolicy(button) {
    console.log('savePolicy triggered');
    try {
        const policyId = button.closest('#policy-form')?.dataset.policyId;
        if (!policyId) {
            console.error('Policy ID not found in form dataset');
            alert('Error: Policy ID not found');
            return;
        }
        console.log('Policy ID:', policyId);

        const policy = policies.find(p => p.id === policyId);
        if (!policy) {
            console.error(`Policy with ID ${policyId} not found`);
            alert('Error: Policy not found');
            return;
        }
        console.log('Policy found:', policy);

        const form = button.closest('#policy-form');
        if (!form) {
            console.error('Policy form not found');
            alert('Error: Policy form not found');
            return;
        }
        console.log('Form found');

        // Retrieve form values
        const policyName = form.querySelector('.policy-name')?.value || '';
        const policyComment = form.querySelector('.policy-comment')?.value || '';
        const action = form.querySelector('.action')?.value || 'accept';
        const sslSshProfile = form.querySelector('.ssl-ssh-profile')?.value || '';
        const webfilterProfile = form.querySelector('.webfilter-profile')?.value || '';
        const applicationList = form.querySelector('.application-list')?.value || '';
        const ipsSensor = form.querySelector('.ips-sensor')?.value || '';
        const logtraffic = form.querySelector('.logtraffic')?.value || 'all';
        const logtrafficStart = form.querySelector('.logtraffic-start')?.value || 'enable';
        const autoAsicOffload = form.querySelector('.auto-asic-offload')?.value || 'enable';
        const nat = form.querySelector('.nat')?.value || 'disable';

        console.log('Form values:', {
            policyName,
            policyComment,
            action,
            sslSshProfile,
            webfilterProfile,
            applicationList,
            ipsSensor,
            logtraffic,
            logtrafficStart,
            autoAsicOffload,
            nat
        });

        // Update policy
        policy.name = policyName;
        policy.comment = policyComment;
        policy.action = action;
        policy.ssl_ssh_profile = sslSshProfile;
        policy.webfilter_profile = webfilterProfile;
        policy.application_list = applicationList;
        policy.ips_sensor = ipsSensor;
        policy.logtraffic = logtraffic;
        policy.logtraffic_start = logtrafficStart;
        policy.auto_asic_offload = autoAsicOffload;
        policy.nat = nat;

        console.log('Policy updated:', policy);

        // Refresh UI
        renderPolicyList();
        selectPolicy(policyId);
        console.log('Policy saved successfully');
    } catch (error) {
        console.error('Error in savePolicy:', error);
        alert('Error saving policy: ' + error.message);
    }
}

function clonePolicy(button) {
    const policyId = button.closest('#policy-form')?.dataset.policyId || button.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for cloning policy');
        return;
    }
    fetch('/clone_policy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ policy_id: policyId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            policies.push({
                id: data.new_policy.policy_id,
                name: data.new_policy.policy_name,
                comment: data.new_policy.policy_comment,
                srcInterfaces: data.new_policy.src_interfaces,
                dstInterfaces: data.new_policy.dst_interfaces,
                srcAddresses: data.new_policy.src_addresses,
                dstAddresses: data.new_policy.dst_addresses,
                services: data.new_policy.services,
                action: data.new_policy.action,
                ssl_ssh_profile: data.new_policy.ssl_ssh_profile,
                webfilter_profile: data.new_policy.webfilter_profile,
                application_list: data.new_policy.application_list,
                ips_sensor: data.new_policy.ips_sensor,
                logtraffic: data.new_policy.logtraffic,
                logtraffic_start: data.new_policy.logtraffic_start,
                auto_asic_offload: data.new_policy.auto_asic_offload,
                nat: data.new_policy.nat
            });
            renderPolicyList();
            selectPolicy(data.new_policy.policy_id);
        } else {
            console.error('Error cloning policy:', data.error);
            alert('Error cloning policy: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error cloning policy:', error);
        alert('Error cloning policy');
    });
}

function clearForm(button) {
    const form = button ? button.closest('#policy-form') : document.getElementById('policy-form');
    if (!form) {
        console.error('Policy form not found for clearing');
        return;
    }
    form.querySelector('.policy-name').value = '';
    form.querySelector('.policy-comment').value = '';
    form.querySelector('.action').value = 'accept';
    form.querySelector('.ssl-ssh-profile').value = '';
    form.querySelector('.webfilter-profile').value = '';
    form.querySelector('.application-list').value = '';
    form.querySelector('.ips-sensor').value = '';
    form.querySelector('.logtraffic').value = 'all';
    form.querySelector('.logtraffic-start').value = 'enable';
    form.querySelector('.auto-asic-offload').value = 'enable';
    form.querySelector('.nat').value = 'disable';
    form.querySelector('.src-interfaces').innerHTML = '';
    form.querySelector('.dst-interfaces').innerHTML = '';
    form.querySelector('.src-addresses').innerHTML = '';
    form.querySelector('.dst-addresses').innerHTML = '';
    form.querySelector('.services').innerHTML = '';

    const policyId = form.dataset.policyId;
    const policy = policies.find(p => p.id === policyId);
    if (policy) {
        policy.srcInterfaces = [];
        policy.dstInterfaces = [];
        policy.srcAddresses = [];
        policy.dstAddresses = [];
        policy.services = [];
    }
}

function saveTemplate() {
    const templateName = document.getElementById('template-name')?.value;
    if (!templateName) {
        console.error('Template name not provided');
        alert('Please enter a template name');
        return;
    }
    const formData = new FormData();
    formData.append('template_name', templateName);
    formData.append('policies', JSON.stringify(policies.map(p => ({
        policy_id: p.id,
        policy_name: p.name,
        policy_comment: p.comment,
        src_interfaces: p.srcInterfaces,
        dst_interfaces: p.dstInterfaces,
        src_addresses: p.srcAddresses,
        dst_addresses: p.dstAddresses,
        services: p.services,
        action: p.action,
        ssl_ssh_profile: p.ssl_ssh_profile,
        webfilter_profile: p.webfilter_profile,
        application_list: p.application_list,
        ips_sensor: p.ips_sensor,
        logtraffic: p.logtraffic,
        logtraffic_start: p.logtraffic_start,
        auto_asic_offload: p.auto_asic_offload,
        nat: p.nat
    }))));

    fetch('/save_template', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
        loadTemplateList();
    })
    .catch(error => {
        console.error('Error saving template:', error);
        alert('Error saving template');
    });
}

function loadTemplateList() {
    fetch('/load_templates')
    .then(response => response.json())
    .then(data => {
        const select = document.getElementById('template-select');
        if (!select) {
            console.error('Template select element not found');
            return;
        }
        select.innerHTML = '<option value="">Select Template</option>';
        data.templates.forEach(template => {
            const option = document.createElement('option');
            option.value = template;
            option.textContent = template;
            select.appendChild(option);
        });

        // If a pre-selected template exists, set it in the dropdown
        if (window.preselectedTemplate) {
            select.value = window.preselectedTemplate;
            loadTemplate();
        }
    })
    .catch(error => {
        console.error('Error loading templates:', error);
    });
}

function loadTemplate() {
    const templateName = document.getElementById('template-select')?.value;
    if (!templateName) {
        console.error('No template selected');
        alert('Please select a template');
        return;
    }
    fetch(`/get_template/${templateName}`)
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            policies = data.data.policies.map(p => ({
                id: p.policy_id,
                name: p.policy_name,
                comment: p.policy_comment,
                srcInterfaces: p.src_interfaces,
                dstInterfaces: p.dst_interfaces,
                srcAddresses: p.src_addresses,
                dstAddresses: p.dst_addresses,
                services: p.services,
                action: p.action,
                ssl_ssh_profile: p.ssl_ssh_profile,
                webfilter_profile: p.webfilter_profile,
                application_list: p.application_list,
                ips_sensor: p.ips_sensor,
                logtraffic: p.logtraffic,
                logtraffic_start: p.logtraffic_start,
                auto_asic_offload: p.auto_asic_offload,
                nat: p.nat
            }));

            // Update global config variables with template data
            interfaces = data.config.interfaces || [];
            addresses = data.config.addresses || [];
            services = data.config.services || [];
            serviceGroups = data.config.service_groups || {};
            sslSshProfiles = data.config.ssl_ssh_profiles || [];
            webfilterProfiles = data.config.webfilter_profiles || [];
            applicationLists = data.config.application_lists || [];
            ipsSensors = data.config.ips_sensors || [];

            // Merge with existing config data if available
            try {
                fetch('/parse_config', { method: 'GET' })
                    .then(res => res.json())
                    .then(config => {
                        interfaces = [...new Set([...interfaces, ...(config.interfaces || [])])];
                        addresses = [...new Set([...addresses, ...(config.addresses || [])])];
                        services = [...services, ...(config.services || []).filter(s => !services.some(existing => existing.name === s.name))];
                        serviceGroups = { ...serviceGroups, ...(config.service_groups || {}) };
                        sslSshProfiles = [...new Set([...sslSshProfiles, ...(config.ssl_ssh_profiles || [])])];
                        webfilterProfiles = [...new Set([...webfilterProfiles, ...(config.webfilter_profiles || [])])];
                        applicationLists = [...new Set([...applicationLists, ...(config.application_lists || [])])];
                        ipsSensors = [...new Set([...ipsSensors, ...(config.ips_sensors || [])])];
                        updateDropdowns();
                        renderPolicyList();
                        if (policies.length > 0) {
                            selectPolicy(policies[0].id);
                        }
                        // Set the template name in the Edit Template input field
                        const templateNameInput = document.getElementById('template-name');
                        if (templateNameInput) {
                            templateNameInput.value = templateName;
                        }
                        alert(`Template '${templateName}' loaded successfully`);
                    })
                    .catch(() => {
                        updateDropdowns();
                        renderPolicyList();
                        if (policies.length > 0) {
                            selectPolicy(policies[0].id);
                        }
                        // Set the template name in the Edit Template input field even if config merge fails
                        const templateNameInput = document.getElementById('template-name');
                        if (templateNameInput) {
                            templateNameInput.value = templateName;
                        }
                        alert(`Template '${templateName}' loaded successfully`);
                    });
            } catch (error) {
                console.error('Error merging config data:', error);
                updateDropdowns();
                renderPolicyList();
                if (policies.length > 0) {
                    selectPolicy(policies[0].id);
                }
                // Set the template name in the Edit Template input field even if an error occurs
                const templateNameInput = document.getElementById('template-name');
                if (templateNameInput) {
                    templateNameInput.value = templateName;
                }
                alert(`Template '${templateName}' loaded successfully`);
            }
        } else {
            console.error('Error loading template:', data.error);
            alert('Error loading template: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error loading template:', error);
        alert('Error loading template');
    });
}

function cloneTemplate() {
    const templateName = document.getElementById('template-select')?.value;
    if (!templateName) {
        console.error('No template selected for cloning');
        alert('Please select a template to clone');
        return;
    }
    fetch(`/clone_template/${templateName}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert(`Template cloned as ${data.new_template_name}`);
            loadTemplateList();
        } else {
            console.error('Error cloning template:', data.error);
            alert('Error cloning template: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error cloning template:', error);
        alert('Error cloning template');
    });
}

function deleteTemplate() {
    const templateName = document.getElementById('template-select')?.value;
    if (!templateName) {
        console.error('No template selected for deletion');
        alert('Please select a template');
        return;
    }
    if (confirm(`Are you sure you want to delete ${templateName}?`)) {
        fetch(`/delete_template/${templateName}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            loadTemplateList();
            // Clear the template name input field after deletion
            const templateNameInput = document.getElementById('template-name');
            if (templateNameInput) {
                templateNameInput.value = '';
            }
        })
        .catch(error => {
            console.error('Error deleting template:', error);
            alert('Error deleting template');
        });
    }
}

function renameTemplate() {
    const oldName = document.getElementById('template-select')?.value;
    const newName = document.getElementById('template-name')?.value;

    if (!oldName) {
        console.error('No template selected for renaming');
        alert('Please select a template to rename');
        return;
    }
    if (!newName) {
        console.error('New template name not provided');
        alert('Please enter a new template name');
        return;
    }
    if (oldName === newName) {
        console.warn('Old and new template names are the same');
        alert('The new template name is the same as the current name');
        return;
    }

    fetch('/rename_template', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_name: oldName, new_name: newName })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert(`Template renamed to ${newName}`);
            window.preselectedTemplate = newName; // Set preselected template to the new name
            loadTemplateList(); // Refresh the template list and re-select the renamed template
        } else {
            console.error('Error renaming template:', data.error);
            alert('Error renaming template: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error renaming template:', error);
        alert('Error renaming template');
    });
}

function copyShortUrl() {
    const templateName = document.getElementById('template-select')?.value;
    if (!templateName) {
        console.error('No template selected for copying short URL');
        alert('Please select a template to copy its short URL');
        return;
    }

    // Construct the relative template URL
    const templateUrl = `/get_template/${templateName}`;
    console.log(`Generating short URL for: ${templateUrl}`);

    // Call the /shorten_url endpoint
    fetch('/shorten_url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: templateUrl })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            const shortCode = data.short_code;
            const shortUrl = `${window.location.origin}/s/${shortCode}`;
            console.log(`Short URL generated: ${shortUrl}`);

            // Copy the short URL to the clipboard
            navigator.clipboard.writeText(shortUrl)
                .then(() => {
                    console.log(`Successfully copied short URL: ${shortUrl}`);
                    alert('Short URL copied to clipboard');
                })
                .catch(error => {
                    console.error('Error copying short URL:', error.message);
                    if (error.message.includes('secure context')) {
                        console.error('Clipboard API requires a secure context (HTTPS or localhost). Ensure the page is served over HTTPS.');
                        alert('Error copying short URL: This feature requires a secure context (HTTPS or localhost).');
                    } else if (error.message.includes('permission')) {
                        console.error('Clipboard access denied. Check browser permissions for clipboard access.');
                        alert('Error copying short URL: Clipboard access denied. Please allow clipboard permissions in your browser.');
                    } else {
                        alert('Error copying short URL: ' + error.message);
                    }
                });
        } else {
            console.error('Error generating short URL:', data.error);
            alert('Error generating short URL: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error generating short URL:', error);
        alert('Error generating short URL');
    });
}

function importConfig() {
    const fileInput = document.getElementById('config-file');
    if (!fileInput?.files.length) {
        console.error('No config file selected');
        alert('Please select a file');
        return;
    }
    const formData = new FormData();
    formData.append('config_file', fileInput.files[0]);

    fetch('/parse_config', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        interfaces = data.interfaces || [];
        addresses = data.addresses || [];
        services = data.services || [];
        serviceGroups = data.service_groups || {};
        sslSshProfiles = data.ssl_ssh_profiles || [];
        webfilterProfiles = data.webfilter_profiles || [];
        applicationLists = data.application_lists || [];
        ipsSensors = data.ips_sensors || [];
        
        updateDropdowns();
        renderPolicyList();
        if (policies.length > 0) {
            selectPolicy(policies[0].id);
        }
        alert('Configuration imported successfully');
    })
    .catch(error => {
        console.error('Error importing config:', error);
        alert('Error importing config');
    });
}

function generatePolicies() {
    if (!policies.length) {
        console.error('No policies to generate');
        alert('No policies to generate');
        return;
    }
    const formData = new FormData();
    formData.append('policies', JSON.stringify(policies.map(p => ({
        policy_id: p.id,
        policy_name: p.name,
        policy_comment: p.comment,
        src_interfaces: p.srcInterfaces,
        dst_interfaces: p.dstInterfaces,
        src_addresses: p.srcAddresses,
        dst_addresses: p.dstAddresses,
        services: p.services,
        action: p.action,
        ssl_ssh_profile: p.ssl_ssh_profile,
        webfilter_profile: p.webfilter_profile,
        application_list: p.application_list,
        ips_sensor: p.ips_sensor,
        logtraffic: p.logtraffic,
        logtraffic_start: p.logtraffic_start,
        auto_asic_offload: p.auto_asic_offload,
        nat: p.nat
    }))));

    fetch('/generate_policy', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('output1').textContent = data.outputs.map(o => o.output1).join('\n\n');
        document.getElementById('output2').textContent = data.outputs.map(o => o.output2).join('\n\n');
        document.getElementById('output3').textContent = data.outputs.map(o => o.output3).join('\n\n');
    })
    .catch(error => {
        console.error('Error generating policies:', error);
        alert('Error generating policies');
    });
}

function copyOutput(outputId) {
    const outputElement = document.getElementById(outputId);
    if (!outputElement) {
        console.error(`Output element ${outputId} not found`);
        return;
    }
    const text = outputElement.textContent;
    if (!text) {
        console.error(`No content to copy for element ${outputId}`);
        alert('No content to copy');
        return;
    }
    navigator.clipboard.writeText(text)
        .then(() => {
            console.log(`Successfully copied content for ${outputId}`);
            alert('Output copied to clipboard');
        })
        .catch(error => {
            console.error('Error copying output:', error.message);
            if (error.message.includes('secure context')) {
                console.error('Clipboard API requires a secure context (HTTPS or localhost). Ensure the page is served over HTTPS.');
                alert('Error copying output: This feature requires a secure context (HTTPS or localhost).');
            } else if (error.message.includes('permission')) {
                console.error('Clipboard access denied. Check browser permissions for clipboard access.');
                alert('Error copying output: Clipboard access denied. Please allow clipboard permissions in your browser.');
            } else {
                alert('Error copying output: ' + error.message);
            }
        });
}

function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    const toggleButton = document.getElementById('theme-toggle');
    toggleButton.textContent = newTheme === 'dark' ? '☀️ Light Mode' : '🌙 Dark Mode';
    toggleButton.setAttribute('aria-label', `Toggle ${newTheme === 'dark' ? 'light' : 'dark'} mode`);
}

document.addEventListener('DOMContentLoaded', () => {
    // Apply saved theme or default to light
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    const toggleButton = document.getElementById('theme-toggle');
    toggleButton.textContent = savedTheme === 'dark' ? '☀️ Light Mode' : '🌙 Dark Mode';
    toggleButton.setAttribute('aria-label', `Toggle ${savedTheme === 'dark' ? 'light' : 'dark'} mode`);

    loadTemplateList();
    // Only add a new policy if no pre-selected template is provided
    if (!window.preselectedTemplate) {
        addPolicy();
    }
    updateDropdowns();
});