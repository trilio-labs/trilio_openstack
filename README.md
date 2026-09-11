# Trilio for OpenStack Ansible Collection (`trilio.trilio_openstack`)

An Ansible Collection for operating and automating **Trilio for OpenStack** (TrilioVault / Workload Manager) backup and recovery workflows.

This collection provides purpose-built modules for managing backup targets, backup target types, workloads, snapshot schedules, full and incremental backups, and restores, designed to work seamlessly alongside standard OpenStack Ansible modules (such as `openstack.cloud`).

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

## Trilio 6.2+ & Dynamic Mounting Service (DMS)

Trilio 6.2 introduces a major architectural enhancement: the **Dynamic Mounting Service (DMS)**.

### How DMS Works
* **On-Demand Mounting**: Prior to Trilio 6.2, backup targets required static mounts and ran a dedicated container per backup target on every compute and controller node. In Trilio 6.2+, DMS centralizes mount management into a single daemon per node, dynamically mounting storage only when a backup or restore job executes and unmounting it when completed.
* **API-Driven Target Creation**: With DMS, backup targets (`/backup_targets`) and backup target types (`/backup_target_types`) are created, updated, and deleted directly through the Trilio Workload Manager API.
* **Backend Reachability Status**: The `status` attribute of backup targets is managed by DMS and reports backend reachability (`online` / `offline`) without requiring a permanent OS mount.

### Zero-Credential Security with OpenStack Barbican
In Trilio 6.2+, **plaintext S3 credentials are no longer accepted in API request bodies**. Instead:
1. S3 access credentials (access key, secret key, endpoint, and bucket) must be stored in the **OpenStack Barbican Key Manager** service.
2. The resulting Barbican secret URL (`secret_ref`, e.g. `https://barbican:9311/v1/secrets/<uuid>`) is passed to the Trilio API.
3. DMS securely fetches the credentials from Barbican at mount time using the requesting job's Keystone token.

Rather than requiring manual out-of-band secret creation and URL copying, the included [`playbooks/create_backup_target_s3.yml`](file:///Users/kevinjackson/Trilio/Ansible/ansible_collections/trilio/trilio_openstack/playbooks/create_backup_target_s3.yml) automates this: it prompts for credentials (or reads from Ansible Vault / environment), registers the secret payload in Barbican using standard Ansible OpenStack automation (`openstack.cloud.resource` or CLI), and immediately feeds the resulting `secret_ref` URL to Trilio.

### Role-Based Access Control (RBAC) & Personas

Understanding the separation of responsibilities between cloud administrators and end-users is central to Trilio operations:

| Persona / Role | Permitted Actions | Associated Modules & Playbooks |
| :--- | :--- | :--- |
| **Cloud Administrator** (`admin` role) | • Create, modify, and delete NFS and S3 Backup Targets via DMS.<br>• Create Backup Target Types (BTT) and assign project/tenant access.<br>• Manage infrastructure Barbican secrets for S3 backends.<br>• Query targets across the entire cloud (`all_projects: true`). | • `trilio.trilio_openstack.backup_target`<br>• `trilio.trilio_openstack.backup_target_info`<br>• `playbooks/create_backup_target_nfs.yml`<br>• `playbooks/create_backup_target_s3.yml` |
| **End User / Tenant** (Project Member) | • Create, modify, and delete Workloads (protection plans).<br>• Choose which administrator-configured Backup Target Type (`backup_target_type`) to store backups on.<br>• Query workload details, snapshot history, and status within authorized projects. | • `trilio.trilio_openstack.workload`<br>• `trilio.trilio_openstack.workload_info`<br>• `playbooks/create_workload.yml` |

> [!IMPORTANT]
> **Backup Target Creation is Admin-Only:** End users cannot create or mount new storage targets (`nfs` or `s3`). Administrators establish targets centrally and expose them to projects via Backup Target Types (BTT). End users then select which BTT to use when creating their workloads.

---

## Security Best Practices

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
5. **Store S3 Credentials in Barbican**: Never store AWS access keys or S3 secrets in playbooks. Use `openstack secret store` or Terraform to register secrets in Barbican, passing only the `secret_ref` URL.

---

## Prerequisites

### Controller / Execution Environment Requirements
* **Ansible**: `ansible-core >= 2.12.0` (compatible with Ansible 2.9+)
* **Python**: Python 3.8+
* **Trilio**: Trilio for OpenStack >= 6.2 (required for DMS backup target APIs)
* **Ansible Collections**:
  * `openstack.cloud >= 2.1.0` (required for modern `openstacksdk` compatibility and dual-collection workflows)
* **Python Libraries**:
  * `openstacksdk >= 1.0.0` (standard SDK for OpenStack Ansible)
  * `requests >= 2.25.0`
  * `keystoneauth1 >= 4.0.0`

Install Python dependencies:
```bash
pip install -r requirements.txt
```

Install Ansible collection dependencies:
```bash
ansible-galaxy collection install -r requirements.yml
```

---

## Module Reference: `trilio.trilio_openstack.backup_target`

Manages the lifecycle (`state: present | absent`) of Trilio Backup Targets (NFS or S3) and their associated Backup Target Types (BTT) using Trilio 6.2+ Dynamic Mounting Service (DMS) API calls.

> **Access Level:** **Administrator Only (`admin` role)**. Adding, modifying, or deleting storage targets is reserved for cloud administrators.

> **Note:** Also accessible via alias `trilio.trilio_openstack.trilio_backup_target`.

### Parameter Reference & Variables

| Variable / Parameter | Type | Default | Choices / Aliases | Description |
| :--- | :--- | :--- | :--- | :--- |
| `state` | `str` | `present` | `present`, `absent` | Desired state of the backup target. |
| `target_type` | `str` | `None` | `nfs`, `s3` (alias: `type`) | Storage backend type. Required when `state=present` and creating a new target. |
| `name` | `str` | `None` | | Target identifier or BTT name to query or create. |
| `backup_target_id` | `str` | `None` | alias: `id` | Specific UUID of an existing backup target to update or delete. |
| `filesystem_export` | `str` | `None` | | NFS filesystem export path (e.g. `192.168.10.50:/var/nfs/trilio`). Required when `target_type=nfs` and `state=present`. |
| `nfs_mount_opts` | `str` | `None` | | NFS mount options string (e.g. `nolock,soft,timeo=600,intr,lookupcache=none,nfsvers=3,retrans=10`). |
| `s3_endpoint_url` | `str` | `None` | | S3 endpoint URL (e.g. `https://s3.eu-west-1.amazonaws.com`). Required when `target_type=s3` and `state=present`. |
| `s3_bucket` | `str` | `None` | | S3 bucket name. Required when `target_type=s3` and `state=present`. |
| `secret_ref` | `str` | `None` | | OpenStack Barbican secret URL referencing S3 access credentials. Required for S3 in Trilio 6.2+ DMS. |
| `btt_name` | `str` | `None` | | Name of the Backup Target Type (BTT) to link/create. Defaults to `name` or export/bucket if omitted. |
| `is_default` | `bool` | `false` | | Whether this backup target should be marked as the default backup target. |
| `immutable` | `bool` | `false` | | Whether S3 Object Lock (immutability) is enabled on the target bucket. |
| `metadata` | `dict` | `None` | | Metadata key-value pairs associated with the backup target. |
| `require_dms` | `bool` | `true` | | Enforces verification that the Trilio API supports DMS (Trilio 6.2+). Fails early on older Trilio releases. |
| `cloud` | `raw` | `None` | | Named cloud in `clouds.yaml` or cloud configuration dictionary. |
| `auth` | `dict` | `None` | `no_log: true` | Keystone authentication credentials dictionary. |
| `auth_type` | `str` | `None` | | Keystone auth plugin name (e.g. `password`, `v3applicationcredential`). |
| `region_name` | `str` | `None` | | OpenStack region name to query. |
| `interface` | `str` | `public` | `public`, `internal`, `admin` | Keystone catalog endpoint interface. |
| `validate_certs` | `bool` | `true` | alias: `verify` | Whether to validate SSL/TLS certificates. |
| `timeout` | `int` | `180` | | HTTP request timeout in seconds. |
| `trilio_endpoint` | `str` | `None` | | Explicit URL override for Trilio Workload Manager API. |

### Return Values

| Return Field | Type | Description |
| :--- | :--- | :--- |
| `backup_target` | `dict` | Dictionary containing target details (`id`, `type`, `filesystem_export`, `s3_endpoint_url`, `s3_bucket`, `secret_ref`, `btt_name`, `status`, `is_default`, `immutable`, `metadata`). |
| `changed` | `bool` | Whether the target was created, updated, or removed. |

---

## Module Reference: `trilio.trilio_openstack.workload`

Manages the lifecycle (`state: present | absent`) of Trilio backup workloads (protection plans), instance membership, backup target types, and snapshot job schedules.

> **Access Level:** **End User / Tenant (Project Member)**. Application owners create workloads to protect their VMs and choose from available administrator-provisioned Backup Target Types (BTT) via `backup_target_type`.

> **Note:** Also accessible via alias `trilio.trilio_openstack.trilio_workload`.

### Parameter Reference & Variables

| Variable / Parameter | Type | Default | Choices / Aliases | Description |
| :--- | :--- | :--- | :--- | :--- |
| `state` | `str` | `present` | `present`, `absent` | Desired state of the workload. |
| `name` | `str` | `None` | | Name of the workload. Required when `state=present` and creating a new workload. |
| `workload_id` | `str` | `None` | alias: `id` | Specific UUID of an existing workload to update or delete. |
| `description` | `str` | `None` | | Description of the workload and its purpose. |
| `workload_type` | `str` | `None` | alias: `workload_type_id` | Workload type name (`Parallel` or `Serial`) or type UUID. Defaults to Parallel if omitted. |
| `instances` | `list` | `[]` | | List of OpenStack compute instance (VM) UUIDs or dictionaries (`id` or `instance-id`) to protect. |
| `backup_target_type` | `str` | `None` | aliases: `backup_target_types`, `btt` | Name or UUID of the Backup Target Type (BTT) to use as the backup destination. |
| `jobschedule` | `dict` | `None` | | Snapshot schedule configuration dictionary (`enabled`, `interval`, `start_time`, `timezone`, `retention_policy_type`, `retention_policy_value`, `fullbackup_interval`). |
| `metadata` | `dict` | `None` | | Metadata key-value dictionary to attach to the workload. |
| `source_platform` | `str` | `openstack` | | Origin platform identifier (typically `openstack`). |
| `project_id` | `str` | `None` | | OpenStack project UUID to create/manage the workload within (defaults to authenticated token's project). |
| `cloud` | `raw` | `None` | | Named cloud in `clouds.yaml` or cloud configuration dictionary. |
| `auth` | `dict` | `None` | `no_log: true` | Keystone authentication credentials dictionary. |
| `validate_certs` | `bool` | `true` | alias: `verify` | Whether to validate SSL/TLS certificates. |
| `timeout` | `int` | `180` | | HTTP request timeout in seconds. |

### Return Values

| Return Field | Type | Description |
| :--- | :--- | :--- |
| `workload` | `dict` | Detailed dictionary of the workload (`id`, `name`, `description`, `status`, `project_id`, `workload_type_id`, `instances`, `jobschedule`, `metadata`). |
| `changed` | `bool` | Whether the workload was created, updated, or removed. |

---

## Module Reference: `trilio.trilio_openstack.backup_target_info`

Queries configured backup targets, their DMS backend reachability status (`online` / `offline`), and associated Backup Target Types (BTT).

> **Note:** Also accessible via alias `trilio.trilio_openstack.trilio_backup_target_info`.

### Parameter Reference & Variables

| Variable / Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `backup_target_id` | `str` | `None` | Specific UUID of a backup target to query (alias: `id`). |
| `name` | `str` | `None` | Filter targets by name or BTT name. |
| `target_type` | `str` | `None` | Filter targets by type (`nfs` or `s3`, alias: `type`). |
| `include_target_types` | `bool` | `true` | Whether to also return the list of configured Backup Target Types (BTT). |
| `require_dms` | `bool` | `true` | Enforces Trilio 6.2+ DMS capability check. |

---

## Module Reference: `trilio.trilio_openstack.workload_info`

Retrieves information, status, instance membership, and schedule details for Trilio workloads in OpenStack.

> **Note:** Also accessible via alias `trilio.trilio_openstack.trilio_workload_info`.

### Target Storage Filtering (NFS & S3)
While the upstream Trilio Workloadmgr REST API historically only exposed `nfs_share` as a server-side query parameter on the `/workloads` endpoint, the `workload_info` module provides comprehensive filtering across **both NFS and S3** backup targets:
* **NFS Filtering (`nfs_share`)**: Passed directly to the upstream Trilio API query parameter for server-side filtering, and verified against workload `storage_url` and `backup_media_target`.
* **S3 Filtering (`s3_bucket`)**: Filters workloads that store backups in the specified S3 bucket (inspecting `storage_url`, `backup_media_target`, and target metadata).
* **Unified Target Filtering (`backup_target`)**: Matches against an NFS filesystem export path, an S3 bucket name, an S3 endpoint URL, or a Backup Target Type name/UUID.
* **Backup Target Type Filtering (`backup_target_type` / `btt`)**: Filters workloads by their assigned Backup Target Type (BTT) name or UUID.

### Parameter Reference & Variables

| Variable / Parameter | Type | Default | Choices / Aliases | Description |
| :--- | :--- | :--- | :--- | :--- |
| `cloud` | `raw` | `None` | | Name of the cloud in `clouds.yaml`. |
| `auth` | `dict` | `None` | `no_log: true` | Keystone authentication dictionary. |
| `name` | `str` | `None` | | Workload name or glob pattern (e.g. `prod-*`) to filter results. |
| `workload_id` | `str` | `None` | alias: `id` | Specific UUID of a workload to query. |
| `all_projects` | `bool` | `false` | | Query workloads across all projects (admin privileges required). |
| `detailed` | `bool` | `true` | | Return full details including VM lists, schedules, and storage URLs. |
| `nfs_share` | `str` | `None` | | Filter workloads stored on a specific backup target NFS share path. |
| `s3_bucket` | `str` | `None` | | Filter workloads stored on a specific backup target S3 bucket. |
| `backup_target` | `str` | `None` | | Unified filter matching an NFS share export path, S3 bucket name, or target name/UUID. |
| `backup_target_type` | `str` | `None` | aliases: `btt`, `backup_target_types` | Filter workloads assigned to a specific Backup Target Type (BTT) name or UUID. |

---

## Playbook Workflows & Examples

All example playbooks reside in the [`playbooks/`](playbooks/) directory:

### 1. Register an NFS Backup Target via DMS (`playbooks/create_backup_target_nfs.yml`)
Registers a new NFS backup target and automatically creates the linked Backup Target Type:
```yaml
- name: Register NFS Backup Target in Trilio
  hosts: localhost
  gather_facts: false

  tasks:
    - name: Ensure NFS backup target exists
      trilio.trilio_openstack.backup_target:
        cloud: openstack
        state: present
        target_type: nfs
        filesystem_export: "192.168.10.50:/var/nfs/trilio"
        nfs_mount_opts: "nolock,soft,timeo=600,intr,lookupcache=none,nfsvers=3,retrans=10"
        btt_name: "primary-nfs-target"
        is_default: true
      register: nfs_target
```

### 2. Register an S3 Backup Target with Barbican Secret (`playbooks/create_backup_target_s3.yml`)
Platform engineers do not need to manually construct Barbican JSON payloads or copy/paste raw `secret_ref` URLs. This playbook accepts S3 credentials securely (interactively with hidden typing, via Ansible Vault, environment variables, or `-e`), registers the secret in OpenStack Barbican using native Ansible OpenStack automation (`openstack.cloud.resource` with CLI fallback), and automatically passes the resolved `secret_ref` URL to Trilio:

```bash
# Interactive prompt (Access key and hidden Secret key):
ansible-playbook -i localhost playbooks/create_backup_target_s3.yml

# Non-interactive via environment variables or Ansible Vault:
export S3_ACCESS_KEY="AKIAIOSFODNN7EXAMPLE"
export S3_SECRET_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
ansible-playbook -i localhost playbooks/create_backup_target_s3.yml

# Non-interactive via extra-vars:
ansible-playbook -i localhost playbooks/create_backup_target_s3.yml \
  -e "s3_access_key=$AWS_ACCESS_KEY_ID s3_secret_key=$AWS_SECRET_ACCESS_KEY"

# Direct mode (using an existing Barbican secret URL directly):
ansible-playbook -i localhost playbooks/create_backup_target_s3.yml \
  -e "barbican_secret_ref=https://barbican.cloud.local:9311/v1/secrets/d12d4d98-11a2-4fa8-b0a3-95c52c4238e1"
```

#### Playbook S3 & Barbican Variable Reference

| Variable | Type | Default | Source / Description |
| :--- | :--- | :--- | :--- |
| `s3_access_key` | `str` | Prompted | S3 Access Key ID. Prompted interactively; falls back to `S3_ACCESS_KEY` or `AWS_ACCESS_KEY_ID`. |
| `s3_secret_key` | `str` | Prompted (Hidden) | S3 Secret Access Key. Prompted with hidden input (`no_log: true`); falls back to `S3_SECRET_KEY` or `AWS_SECRET_ACCESS_KEY`. |
| `s3_bucket` | `str` | `company-openstack-backups` | Target S3 bucket name. Configurable via `TRILIO_S3_BUCKET`. |
| `s3_endpoint` | `str` | `https://s3.eu-west-1.amazonaws.com` | S3 endpoint URL (AWS S3, Ceph RGW, MinIO, Wasabi, etc.). Configurable via `TRILIO_S3_ENDPOINT`. |
| `btt_name` | `str` | `s3-cold-storage` | Trilio Backup Target Type (BTT) name. Configurable via `TRILIO_S3_BTT_NAME`. |
| `barbican_secret_name` | `str` | `secret-key-{{ btt_name }}` | Barbican secret name. Configurable via `TRILIO_BARBICAN_SECRET_NAME`. |
| `barbican_secret_ref` | `str` | `""` | Optional pre-existing Barbican secret URL. If supplied, Barbican secret creation is skipped. Configurable via `TRILIO_BARBICAN_SECRET_REF`. |
| `s3_ssl` | `bool` | `true` | Whether to enable SSL for S3 communication. |
| `s3_ssl_verify` | `bool` | `true` | Whether to verify SSL certificates for S3 communication. |

### 3. Create a Protection Workload (`playbooks/create_workload.yml`)
Creates an automated daily backup workload protecting compute instances:
```yaml
- name: Protect Production Web Servers
  hosts: localhost
  gather_facts: false

  tasks:
    - name: Create Trilio workload
      trilio.trilio_openstack.workload:
        cloud: openstack
        state: present
        name: "production-web-cluster"
        description: "Automated daily backup of web cluster"
        backup_target_type: "primary-nfs-target"
        instances:
          - "28e08d66-8968-45e0-9bc7-5bb83fc44007"
          - "49f19e77-9079-56f1-0cd8-6cc94gd55118"
        jobschedule:
          enabled: true
          interval: "24 hr"
          start_time: "02:00 AM"
          timezone: "UTC"
          retention_policy_type: "Number of Snapshots to Keep"
          retention_policy_value: "30"
          fullbackup_interval: "-1"
```

### 4. End-to-End Discovery & Protection (`playbooks/setup_trilio_end_to_end.yml`)
Combines `openstack.cloud.server_info`, `trilio.trilio_openstack.backup_target`, and `trilio.trilio_openstack.workload` in a unified workflow:
```yaml
- name: Discover VMs and Setup Trilio Protection
  hosts: localhost
  gather_facts: false

  tasks:
    - name: Ensure NFS backup target is registered via DMS
      trilio.trilio_openstack.backup_target:
        cloud: openstack
        state: present
        target_type: nfs
        filesystem_export: "192.168.10.50:/var/nfs/trilio"
        btt_name: "primary-nfs-target"
        is_default: true

    - name: Discover all active compute instances
      openstack.cloud.server_info:
        cloud: openstack
      register: nova_servers

    - name: Create Trilio workload protecting all discovered VMs
      trilio.trilio_openstack.workload:
        cloud: openstack
        state: present
        name: "all-vms-protection-plan"
        backup_target_type: "primary-nfs-target"
        instances: "{{ nova_servers.servers | map(attribute='id') | list }}"
        jobschedule:
          enabled: true
          interval: "24 hr"
          retention_policy_type: "Number of Snapshots to Keep"
          retention_policy_value: "14"
```

---

## Running Tests

Run the unit test suite with Python's `unittest`:
```bash
PYTHONPATH=../../.. python3 -m unittest discover -s tests/unit -v
```

Verify Ansible playbook YAML syntax:
```bash
ansible-playbook --syntax-check playbooks/*.yml
```

---

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
