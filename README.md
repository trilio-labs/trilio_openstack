# Trilio for OpenStack Ansible Collection (`trilio.trilio_openstack`)

An Ansible Collection for operating and automating **Trilio for OpenStack** (TrilioVault / Workload Manager) backup and recovery workflows.

This collection provides purpose-built modules for managing backup targets, workloads, snapshot schedules, full and incremental backups, and restores, designed to work seamlessly alongside standard OpenStack Ansible modules (such as `openstack.cloud`).

---

## Architectural Principles & Authentication

### Seamless OpenStack Integration
This collection **does not reinvent OpenStack authentication**. Instead, it complements existing OpenStack tooling by accepting the identical connection parameters used across the OpenStack Ansible ecosystem:
* **Standard `clouds.yaml`**: Authenticate using `cloud: <cloud_name>` configured in `~/.config/openstack/clouds.yaml` or `/etc/openstack/clouds.yaml`.
* **Standard `auth` Dictionary**: Pass standard Keystone v3 parameters (`auth_url`, `username`, `password`, `project_name`, `user_domain_name`, `project_domain_name`).
* **Modern Application Credentials**: Pass `auth_type: v3applicationcredential` with `application_credential_id` and `application_credential_secret`.
* **Standard Environment Variables**: Automatically consume `OS_AUTH_URL`, `OS_USERNAME`, `OS_PASSWORD`, `OS_PROJECT_NAME`, `OS_APPLICATION_CREDENTIAL_ID`, etc.

### Service Catalog Discovery
When authenticating to Keystone, the collection automatically queries the OpenStack Service Catalog for the Trilio Workload Manager endpoint (searching for service type `workloads`, `workloadmgr`, or `triliovault`) matching the selected `interface` (`public`, `internal`, or `admin`) and `region_name`. An optional `trilio_endpoint` parameter is available if an explicit override is required.

---

## Security Best Practices

> [!CAUTION]
> **Zero Credentials in Git/GitHub:** Never commit passwords, tokens, API keys, or raw `clouds.yaml` files containing credentials into source control.

To ensure production security:
1. **Restrict `clouds.yaml` file permissions**:
   ```bash
   chmod 0600 ~/.config/openstack/clouds.yaml
   ```
2. **Use Environment Variables**: Reference credentials dynamically via Ansible lookups:
   ```yaml
   password: "{{ lookup('ansible.builtin.env', 'OS_PASSWORD') }}"
   ```
3. **Use Ansible Vault**: Encrypt sensitive variables files:
   ```bash
   ansible-vault encrypt credentials.yml
   ```
4. **Use Keystone Application Credentials**: Prefer project-scoped Application Credentials over administrator passwords for automated CI/CD runners.

---

## Prerequisites

### Controller / Execution Environment Requirements
* **Ansible**: `ansible-core >= 2.14.0`
* **Python**: Python 3.9+
* **Python Libraries**:
  * `openstacksdk >= 1.0.0` (standard SDK for OpenStack Ansible)
  * `requests >= 2.25.0`
  * `keystoneauth1 >= 4.0.0`

Install Python dependencies:
```bash
pip install -r requirements.txt
```

---

## Installation

### Including in `requirements.yml`
```yaml
collections:
  - name: trilio.trilio_openstack
    type: git
    source: https://github.com/trilio-labs/trilio_openstack.git
```
Install via:
```bash
ansible-galaxy collection install -r requirements.yml
```

### Local Development / Direct Usage
Ensure this repository resides in your Ansible collections path:
```text
<ansible_collections_path>/trilio/trilio_openstack/
```
Example `ansible.cfg`:
```ini
[defaults]
collections_paths = ./ansible_collections:~/.ansible/collections:/usr/share/ansible/collections
```

---

## Module Reference: `trilio.trilio_openstack.workload_info`

Retrieves information, status, instance membership, and schedule details for Trilio workloads in OpenStack.

> **Note:** The module is also accessible via the alias `trilio.trilio_openstack.trilio_workload_info`.

### Parameter Reference & Variables

| Variable / Parameter | Type | Default | Choices / Aliases | Description |
| :--- | :--- | :--- | :--- | :--- |
| `cloud` | `raw` | `None` | | Name of the cloud in `clouds.yaml`, or a dictionary containing cloud configuration. |
| `auth` | `dict` | `None` | `no_log: true` | Keystone authentication dictionary containing `auth_url`, `username`, `password`, `project_name`, etc. |
| `auth_type` | `str` | `None` | | Authentication plugin name (e.g. `password`, `v3applicationcredential`, `token`). |
| `region_name` | `str` | `None` | | Specific OpenStack region name to query. |
| `interface` | `str` | `public` | `public`, `internal`, `admin` (alias: `endpoint_type`) | Keystone catalog endpoint interface used to locate Trilio WLM API. |
| `validate_certs` | `bool` | `true` | alias: `verify` | Whether to validate SSL/TLS certificates. |
| `ca_cert` | `str` | `None` | alias: `cacert` | Path to CA certificate bundle file. |
| `client_cert` | `str` | `None` | alias: `cert` | Path to SSL client certificate file. |
| `client_key` | `str` | `None` | `no_log: true`, alias: `key` | Path to SSL client private key file. |
| `timeout` | `int` | `180` | | HTTP request timeout in seconds. |
| `api_timeout` | `int` | `None` | | OpenStack SDK client timeout in seconds. |
| `trilio_endpoint` | `str` | `None` | | Explicit override URL for Trilio WLM API (e.g. `https://tvm.internal:8780/v1`). If omitted, discovered via Keystone. |
| `name` | `str` | `None` | | Workload name or glob pattern (e.g. `prod-*`) to filter results. |
| `workload_id` | `str` | `None` | alias: `id` | Specific UUID of a workload to query. |
| `all_projects` | `bool` | `false` | | When `true`, queries workloads across all projects (requires OpenStack cloud administrator permissions). |
| `project_id` | `str` | `None` | | OpenStack project UUID to query workloads for. Defaults to the authenticated token's project ID. |
| `detailed` | `bool` | `true` | | When `true`, calls `/workloads/detail` to return protected VM lists, job schedules, and storage targets. |
| `nfs_share` | `str` | `None` | | Filter workloads stored on a specific backup target NFS share path. |

---

### Return Values

The module returns a dictionary with `changed: false` and a list named `workloads`:

```yaml
workloads:
  - id: "7b47b4e8-8db9-4670-8b1e-0679815049cf"
    name: "production-web-cluster"
    description: "Nightly backup of web frontend VMs"
    status: "available"
    project_id: "c38ff02cb5794cb4b6e5e8e45f9db1d6"
    user_id: "3c368d4078bd44a0bdf5dbceeeebef31"
    workload_type_id: "272f3105-fhang-4b36-81cf-fb15b8054c25"
    storage_url: "192.168.10.50:/var/nfs/trilio"
    instances:
      - id: "28e08d66-8968-45e0-9bc7-5bb83fc44007"
        name: "web-01"
      - id: "49f19e77-9079-56f1-0cd8-6cc94gd55118"
        name: "web-02"
    jobschedule:
      enabled: true
      interval: "24 hr"
      retention_policy_type: "Number of Snapshots to Keep"
      retention_policy_value: "30"
      fullbackup_interval: "-1"
      timezone: "UTC"
    metadata: {}
    created_at: "2026-09-01T08:30:00.000000"
    updated_at: "2026-09-10T02:00:00.000000"
```

---

## Playbook Examples

All example playbooks are available in the [`playbooks/`](playbooks/) directory:

### 1. Authenticating via Environment Variables (`playbooks/list_workloads_env.yml`)
When you have sourced your OpenStack RC file (`source openrc.sh`):
```yaml
- name: List Trilio workloads using active environment variables
  hosts: localhost
  gather_facts: false

  tasks:
    - name: Fetch workloads
      trilio.trilio_openstack.workload_info:
      register: result

    - name: Print discovered workloads
      ansible.builtin.debug:
        msg: "Discovered {{ result.workloads | length }} workload(s): {{ result.workloads | map(attribute='name') | list }}"
```

### 2. Authenticating via `clouds.yaml` (`playbooks/list_workloads_clouds_yaml.yml`)
When using `~/.config/openstack/clouds.yaml`:
```yaml
- name: List Trilio workloads using clouds.yaml
  hosts: localhost
  gather_facts: false

  vars:
    cloud_name: "{{ lookup('ansible.builtin.env', 'OS_CLOUD') | default('openstack', true) }}"

  tasks:
    - name: Fetch workloads
      trilio.trilio_openstack.workload_info:
        cloud: "{{ cloud_name }}"
      register: result

    - name: Print discovered workloads
      ansible.builtin.debug:
        msg: "Discovered {{ result.workloads | length }} workload(s): {{ result.workloads | map(attribute='name') | list }}"
```

### 3. Authenticating via Explicit `auth` Dictionary (`playbooks/list_workloads_auth_dict.yml`)
When credentials are passed dynamically from variables or Ansible Vault:
```yaml
- name: List Trilio workloads using Keystone Auth Dictionary
  hosts: localhost
  gather_facts: false

  tasks:
    - name: Fetch workloads using Keystone v3 credentials
      trilio.trilio_openstack.workload_info:
        auth:
          auth_url: "{{ lookup('ansible.builtin.env', 'OS_AUTH_URL') }}"
          username: "{{ lookup('ansible.builtin.env', 'OS_USERNAME') }}"
          password: "{{ lookup('ansible.builtin.env', 'OS_PASSWORD') }}"
          project_name: "{{ lookup('ansible.builtin.env', 'OS_PROJECT_NAME') | default(lookup('ansible.builtin.env', 'OS_TENANT_NAME'), true) }}"
          user_domain_name: "{{ lookup('ansible.builtin.env', 'OS_USER_DOMAIN_NAME') | default('Default', true) }}"
          project_domain_name: "{{ lookup('ansible.builtin.env', 'OS_PROJECT_DOMAIN_NAME') | default('Default', true) }}"
        validate_certs: "{{ (lookup('ansible.builtin.env', 'OS_INSECURE') | lower != 'true') and (lookup('ansible.builtin.env', 'OS_VERIFY') | default('true', true) | bool) }}"
      register: result
```

### 4. Authenticating via Keystone Application Credentials (`playbooks/list_workloads_app_cred.yml`)
```yaml
- name: List Trilio workloads using Application Credentials
  hosts: localhost
  gather_facts: false

  tasks:
    - name: Fetch workloads
      trilio.trilio_openstack.workload_info:
        auth_type: v3applicationcredential
        auth:
          auth_url: "{{ lookup('ansible.builtin.env', 'OS_AUTH_URL') }}"
          application_credential_id: "{{ lookup('ansible.builtin.env', 'OS_APPLICATION_CREDENTIAL_ID') | default(omit, true) }}"
          application_credential_name: "{{ lookup('ansible.builtin.env', 'OS_APPLICATION_CREDENTIAL_NAME') | default(omit, true) }}"
          application_credential_secret: "{{ lookup('ansible.builtin.env', 'OS_APPLICATION_CREDENTIAL_SECRET') }}"
        validate_certs: "{{ (lookup('ansible.builtin.env', 'OS_INSECURE') | lower != 'true') and (lookup('ansible.builtin.env', 'OS_VERIFY') | default('true', true) | bool) }}"
      register: result
```

### 5. Complementary Workflow with `openstack.cloud` (`playbooks/list_workloads_combined.yml`)
Demonstrates how both collections work together in a single playbook to cross-reference OpenStack compute instances with Trilio backup workloads (supports both `clouds.yaml` and active environment variables seamlessly):
```yaml
- name: Audit OpenStack VMs and Trilio Protection
  hosts: localhost
  gather_facts: false

  vars:
    cloud_name: "{{ lookup('ansible.builtin.env', 'OS_CLOUD') | default(omit, true) }}"

  tasks:
    - name: Retrieve all compute instances
      openstack.cloud.server_info:
        cloud: "{{ cloud_name | default(omit) }}"
      register: nova_servers

    - name: Retrieve all Trilio workloads
      trilio.trilio_openstack.workload_info:
        cloud: "{{ cloud_name | default(omit) }}"
        detailed: true
      register: trilio_workloads

    - name: Build list of protected VM IDs
      ansible.builtin.set_fact:
        protected_ids: >-
          {{
            trilio_workloads.workloads
            | map(attribute='instances')
            | flatten
            | map(attribute='id')
            | list
          }}

    - name: Report protection status per VM
      ansible.builtin.debug:
        msg: "Server {{ item.name }} ({{ item.id }}) is {{ 'PROTECTED' if item.id in protected_ids else 'UNPROTECTED' }}"
      loop: "{{ nova_servers.servers }}"
```

---

## Running Tests

Run the unit test suite with `pytest`:
```bash
PYTHONPATH=../../.. pytest tests/unit/
```

Verify Ansible playbook syntax:
```bash
ansible-playbook --syntax-check playbooks/*.yml
```

---

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
