// scripts.js (Version 1.5)
let policies = [];
let interfaces = [];
let addresses = [];
let services = [];
let serviceGroups = {};
let sslSshProfiles = [];
let webfilterProfiles = [];
let applicationLists = [];
let ipsSensors = [];
let users = [];
let groups = [];

function showNotification(message, type = 'success') {
    const container = document.getElementById('notification-container');
    if (!container) {
        console.error('Notification container not found');
        return;
    }

    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    container.appendChild(notification);

    // Auto-dismiss after 3 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
            notification.remove();
        }, 500); // Match the animation duration
    }, 3000);
}

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
        nat: 'disable',
        users: [],
        groups: []
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

        renderInterfaces(form.querySelector('.src-interfaces .interface-items'), policy.srcInterfaces, 'src');
        renderInterfaces(form.querySelector('.dst-interfaces .interface-items'), policy.dstInterfaces, 'dst');
        renderAddresses(form.querySelector('.src-addresses .address-items'), policy.srcAddresses, 'src');
        renderAddresses(form.querySelector('.dst-addresses .address-items'), policy.dstAddresses, 'dst');
        renderServices(form.querySelector('.services'), policy.services);
        renderUsersGroups(form.querySelector('.src-users-groups .user-group-items'), policy.users, policy.groups);
    } catch (error) {
        console.error('Error in selectPolicy:', error);
    }
}

function renderInterfaces(container, items, type) {
    if (!container) {
        console.error('Interface items container not found');
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
        console.error('Address items container not found');
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

function renderUsersGroups(container, userItems, groupItems) {
    if (!container) {
        console.error('Users/Groups items container not found');
        return;
    }
    container.innerHTML = '';
    [...userItems, ...groupItems].forEach((item, index) => {
        const isUser = userItems.includes(item);
        const div = document.createElement('div');
        div.className = 'user-group-item';
        div.innerHTML = `
            <select onchange="updateUserOrGroup(${index}, this.value)">
                <option value="">Select User/Group</option>
                <optgroup label="Users">
                    ${users.map(user => `<option value="user:${user}" ${isUser && item === user ? 'selected' : ''}>${user}</option>`).join('')}
                </optgroup>
                <optgroup label="Groups">
                    ${groups.map(group => `<option value="group:${group}" ${!isUser && item === group ? 'selected' : ''}>${group}</option>`).join('')}
                </optgroup>
            </select>
            <button onclick="deleteUserOrGroup(${index})">Delete</button>
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

function addSrcUserOrGroup(button) {
    const policyId = button.closest('#policy-form')?.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for adding user or group');
        return;
    }
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }
    policy.users.push('');
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

function updateUserOrGroup(index, value) {
    const policyId = document.getElementById('policy-form')?.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for updating user or group');
        return;
    }
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }
    const [type, name] = value.split(':');
    const totalItems = policy.users.length + policy.groups.length;
    if (index < policy.users.length) {
        if (type === 'user') {
            policy.users[index] = name;
        } else if (type === 'group') {
            policy.users.splice(index, 1);
            policy.groups.splice(index - policy.users.length, 0, name);
        }
    } else {
        const groupIndex = index - policy.users.length;
        if (type === 'group') {
            policy.groups[groupIndex] = name;
        } else if (type === 'user') {
            policy.groups.splice(groupIndex, 1);
            policy.users.splice(index, 0, name);
        }
    }
    selectPolicy(policyId);
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

function deleteUserOrGroup(index) {
    const policyId = document.getElementById('policy-form')?.dataset.policyId;
    if (!policyId) {
        console.error('Policy ID not found for deleting user or group');
        return;
    }
    const policy = policies.find(p => p.id === policyId);
    if (!policy) {
        console.error(`Policy with ID ${policyId} not found`);
        return;
    }
    if (index < policy.users.length) {
        policy.users.splice(index, 1);
    } else {
        policy.groups.splice(index - policy.users.length, 1);
    }
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
            showNotification('Error: Policy ID not found', 'error');
            return;
        }
        console.log('Policy ID:', policyId);

        const policy = policies.find(p => p.id === policyId);
        if (!policy) {
            console.error(`Policy with ID ${policyId} not found`);
            showNotification('Error: Policy not found', 'error');
            return;
        }
        console.log('Policy found:', policy);

        const form = button.closest('#policy-form');
        if (!form) {
            console.error('Policy form not found');
            showNotification('Error: Policy form not found', 'error');
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
        showNotification('Policy saved successfully', 'success');
    } catch (error) {
        console.error('Error in savePolicy:', error);
        showNotification('Error saving policy: ' + error.message, 'error');
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
                nat: data.new_policy.nat,
                users: data.new_policy.users,
                groups: data.new_policy.groups
            });
            renderPolicyList();
            selectPolicy(data.new_policy.policy_id);
            showNotification('Policy cloned successfully', 'success');
        } else {
            console.error('Error cloning policy:', data.error);
            showNotification('Error cloning policy: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Error cloning policy:', error);
        showNotification('Error cloning policy', 'error');
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
    form.querySelector('.src-interfaces .interface-items').innerHTML = '';
    form.querySelector('.dst-interfaces .interface-items').innerHTML = '';
    form.querySelector('.src-addresses .address-items').innerHTML = '';
    form.querySelector('.dst-addresses .address-items').innerHTML = '';
    form.querySelector('.services').innerHTML = '';
    form.querySelector('.src-users-groups .user-group-items').innerHTML = '';

    const policyId = form.dataset.policyId;
    const policy = policies.find(p => p.id === policyId);
    if (policy) {
        policy.srcInterfaces = [];
        policy.dstInterfaces = [];
        policy.srcAddresses = [];
        policy.dstAddresses = [];
        policy.services = [];
        policy.users = [];
        policy.groups = [];
    }
}

function saveTemplate() {
    const templateName = document.getElementById('template-name')?.value;
    if (!templateName) {
        console.error('Template name not provided');
        showNotification('Please enter a template name', 'error');
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
        nat: p.nat,
        users: p.users,
        groups: p.groups
    }))));

    fetch('/save_template', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        showNotification(data.message, 'success');
        loadTemplateList();
    })
    .catch(error => {
        console.error('Error saving template:', error);
        showNotification('Error saving template', 'error');
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
        showNotification('Please select a template', 'error');
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
                nat: p.nat,
                users: p.users || [],
                groups: p.groups || []
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
            users = data.config.users || [];
            groups = data.config.groups || [];

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
                        users = [...new Set([...users, ...(config.users || [])])];
                        groups = [...new Set([...groups, ...(config.groups || [])])];
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
                        showNotification(`Template '${templateName}' loaded successfully`, 'success');
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
                        showNotification(`Template '${templateName}' loaded successfully`, 'success');
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
                showNotification(`Template '${templateName}' loaded successfully`, 'success');
            }
        } else {
            console.error('Error loading template:', data.error);
            showNotification('Error loading template: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Error loading template:', error);
        showNotification('Error loading template', 'error');
    });
}

function cloneTemplate() {
    const templateName = document.getElementById('template-select')?.value;
    if (!templateName) {
        console.error('No template selected for cloning');
        showNotification('Please select a template to clone', 'error');
        return;
    }
    fetch(`/clone_template/${templateName}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            showNotification(`Template cloned as ${data.new_template_name}`, 'success');
            loadTemplateList();
        } else {
            console.error('Error cloning template:', data.error);
            showNotification('Error cloning template: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Error cloning template:', error);
        showNotification('Error cloning template', 'error');
    });
}

function deleteTemplate() {
    const templateName = document.getElementById('template-select')?.value;
    if (!templateName) {
        console.error('No template selected for deletion');
        showNotification('Please select a template', 'error');
        return;
    }
    if (confirm(`Are you sure you want to delete ${templateName}?`)) {
        fetch(`/delete_template/${templateName}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            showNotification(data.message, 'success');
            loadTemplateList();
            // Clear the template name input field after deletion
            const templateNameInput = document.getElementById('template-name');
            if (templateNameInput) {
                templateNameInput.value = '';
            }
        })
        .catch(error => {
            console.error('Error deleting template:', error);
            showNotification('Error deleting template', 'error');
        });
    }
}

function renameTemplate() {
    const oldName = document.getElementById('template-select')?.value;
    const newName = document.getElementById('template-name')?.value;

    if (!oldName) {
        console.error('No template selected for renaming');
        showNotification('Please select a template to rename', 'error');
        return;
    }
    if (!newName) {
        console.error('New template name not provided');
        showNotification('Please enter a new template name', 'error');
        return;
    }
    if (oldName === newName) {
        console.warn('Old and new template names are the same');
        showNotification('The new template name is the same as the current name', 'error');
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
            showNotification(`Template renamed to ${newName}`, 'success');
            window.preselectedTemplate = newName; // Set preselected template to the new name
            loadTemplateList(); // Refresh the template list and re-select the renamed template
        } else {
            console.error('Error renaming template:', data.error);
            showNotification('Error renaming template: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Error renaming template:', error);
        showNotification('Error renaming template', 'error');
    });
}

function copyUrl() {
    const templateName = document.getElementById('template-select')?.value;
    if (!templateName) {
        console.error('No template selected for copying URL');
        showNotification('Please select a template to copy its URL', 'error');
        return;
    }

    // Construct the relative template URL
    const templateUrl = `/get_template/${templateName}`;
    console.log(`Generating URL for: ${templateUrl}`);

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
            console.log(`URL generated: ${shortUrl}`);

            // Copy the URL to the clipboard
            navigator.clipboard.writeText(shortUrl)
                .then(() => {
                    console.log(`Successfully copied URL: ${shortUrl}`);
                    showNotification('URL copied to clipboard', 'success');
                })
                .catch(error => {
                    console.error('Error copying URL:', error.message);
                    if (error.message.includes('secure context')) {
                        console.error('Clipboard API requires a secure context (HTTPS or localhost). Ensure the page is served over HTTPS.');
                        showNotification('Error copying URL: This feature requires a secure context (HTTPS or localhost)', 'error');
                    } else if (error.message.includes('permission')) {
                        console.error('Clipboard access denied. Check browser permissions for clipboard access.');
                        showNotification('Error copying URL: Clipboard access denied. Please allow clipboard permissions in your browser', 'error');
                    } else {
                        showNotification('Error copying URL: ' + error.message, 'error');
                    }
                });
        } else {
            console.error('Error generating URL:', data.error);
            showNotification('Error generating URL: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Error generating URL:', error);
        showNotification('Error generating URL', 'error');
    });
}

function importTemplate(event) {
    const fileInput = event.target;
    if (!fileInput?.files.length) {
        console.error('No template file selected');
        showNotification('Please select a JSON file to import', 'error');
        return;
    }

    const file = fileInput.files[0];
    const reader = new FileReader();

    reader.onload = function(e) {
        try {
            const templateData = JSON.parse(e.target.result);
            if (!templateData.name || !templateData.data || !templateData.data.policies) {
                throw new Error('Invalid template format: Must contain name and data with policies');
            }

            const formData = new FormData();
            formData.append('template_name', templateData.name);
            formData.append('template_data', JSON.stringify(templateData.data));

            fetch('/import_template', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    showNotification(`Template '${templateData.name}' imported successfully`, 'success');
                    loadTemplateList();
                    // Reset the file input
                    fileInput.value = '';
                } else {
                    console.error('Error importing template:', data.error);
                    showNotification('Error importing template: ' + data.error, 'error');
                }
            })
            .catch(error => {
                console.error('Error importing template:', error);
                showNotification('Error importing template', 'error');
            });
        } catch (error) {
            console.error('Error parsing template file:', error);
            showNotification('Error parsing template file: ' + error.message, 'error');
        }
    };

    reader.onerror = function() {
        console.error('Error reading template file');
        showNotification('Error reading template file', 'error');
    };

    reader.readAsText(file);
}

function exportTemplate() {
    const templateName = document.getElementById('template-select')?.value;
    if (!templateName) {
        console.error('No template selected for export');
        showNotification('Please select a template to export', 'error');
        return;
    }

    fetch(`/export_template/${templateName}`)
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Failed to export template');
            });
        }
        return response.blob();
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${templateName}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        showNotification(`Template '${templateName}' exported successfully`, 'success');
    })
    .catch(error => {
        console.error('Error exporting template:', error);
        showNotification('Error exporting template: ' + error.message, 'error');
    });
}

function importConfig() {
    const fileInput = document.getElementById('config-file');
    if (!fileInput?.files.length) {
        console.error('No config file selected');
        showNotification('Please select a file', 'error');
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
        users = data.users || [];
        groups = data.groups || [];
        
        updateDropdowns();
        renderPolicyList();
        if (policies.length > 0) {
            selectPolicy(policies[0].id);
        }
        showNotification('Configuration imported successfully', 'success');
    })
    .catch(error => {
        console.error('Error importing config:', error);
        showNotification('Error importing config', 'error');
    });
}

function generatePolicies() {
    if (!policies.length) {
        console.error('No policies to generate');
        showNotification('No policies to generate', 'error');
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
        nat: p.nat,
        users: p.users,
        groups: p.groups
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
        showNotification('Policies generated successfully', 'success');
    })
    .catch(error => {
        console.error('Error generating policies:', error);
        showNotification('Error generating policies', 'error');
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
        showNotification('No content to copy', 'error');
        return;
    }
    navigator.clipboard.writeText(text)
        .then(() => {
            console.log(`Successfully copied content for ${outputId}`);
            showNotification('Output copied to clipboard', 'success');
        })
        .catch(error => {
            console.error('Error copying output:', error.message);
            if (error.message.includes('secure context')) {
                console.error('Clipboard API requires a secure context (HTTPS or localhost). Ensure the page is served over HTTPS.');
                showNotification('Error copying output: This feature requires a secure context (HTTPS or localhost)', 'error');
            } else if (error.message.includes('permission')) {
                console.error('Clipboard access denied. Check browser permissions for clipboard access.');
                showNotification('Error copying output: Clipboard access denied. Please allow clipboard permissions in your browser', 'error');
            } else {
                showNotification('Error copying output: ' + error.message, 'error');
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
    toggleButton.addEventListener('click', toggleTheme); // Attach the event listener

    loadTemplateList();
    // Only add a new policy if no pre-selected template is provided
    if (!window.preselectedTemplate) {
        addPolicy();
    }
    updateDropdowns();
});