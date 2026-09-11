#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: backup_target
short_description: Manage Trilio for OpenStack Backup Targets and Backup Target Types (BTT)
version_added: "1.1.0"
description:
  - Create, update, and delete Backup Targets (NFS or S3) and their associated Backup Target Types (BTT)
    in Trilio for OpenStack.
  - Adding or modifying backup targets is reserved for OpenStack users with the C(admin) role.
    End users / project tenants cannot create backup targets; they consume targets created by administrators
    by selecting Backup Target Types (BTT) when creating workloads.
  - Requires Trilio version 6.2 or newer, which utilizes the Dynamic Mounting Service (DMS)
    to dynamically manage backup targets via API calls rather than static host mounts.
  - For S3 backup targets, credentials must be stored securely in an OpenStack Barbican secret,
    passing only the C(secret_ref) URL to enforce zero credential leakage into playbooks.
  - Connects to OpenStack using standard OpenStack connection patterns (clouds.yaml, Keystone auth dictionary,
    or environment variables).
notes:
  - "Target management is an administrator-only operation requiring OpenStack C(admin) privileges."
  - "End-users / project tenants should use C(trilio.trilio_openstack.workload) to select from existing Backup Target Types (BTT)."
author:
  - Kevin Jackson (@uksysadmin)
options:
  state:
    description:
      - Desired state of the backup target.
    type: str
    choices: ['present', 'absent']
    default: 'present'
  target_type:
    description:
      - Storage backend type for the backup target. Required when C(state=present) and creating a target.
    type: str
    choices: ['nfs', 's3']
    aliases: ['type']
  name:
    description:
      - Logical identifier or Backup Target Type (BTT) name for the backup target.
    type: str
  backup_target_id:
    description:
      - UUID of an existing backup target to update or delete.
    type: str
    aliases: ['id']
  filesystem_export:
    description:
      - NFS filesystem export path (e.g. C(192.168.1.50:/var/nfs/trilio)).
      - Required when C(target_type=nfs) and C(state=present).
    type: str
  nfs_mount_opts:
    description:
      - Mount options string for NFS shares (e.g. C(nolock,soft,timeo=600,intr,lookupcache=none,nfsvers=3,retrans=10)).
    type: str
  s3_endpoint_url:
    description:
      - Endpoint URL for S3-compatible storage (e.g. C(https://s3.amazonaws.com) or C(https://minio.company.internal:9000)).
      - Required when C(target_type=s3) and C(state=present).
    type: str
  s3_bucket:
    description:
      - S3 bucket name where backup data and metadata are stored.
      - Required when C(target_type=s3) and C(state=present).
    type: str
  secret_ref:
    description:
      - OpenStack Barbican secret URL containing S3 access credentials (e.g. C(https://barbican:9311/v1/secrets/<uuid>)).
      - Required for S3 targets in Trilio 6.2+ DMS. Plaintext credentials are not accepted.
    type: str
  btt_name:
    description:
      - Name for the Backup Target Type (BTT) created and linked to this backup target.
      - If omitted, defaults to C(name) or the filesystem export / S3 bucket name.
    type: str
  is_default:
    description:
      - Whether this backup target should be configured as the default backup target.
    type: bool
    default: false
  immutable:
    description:
      - Whether S3 Object Lock (immutability) is enabled on the target bucket.
    type: bool
    default: false
  metadata:
    description:
      - Metadata key-value dictionary to associate with the backup target.
    type: dict
  require_dms:
    description:
      - Enforces verification that the Trilio API supports the Dynamic Mounting Service (DMS) (Trilio 6.2+).
    type: bool
    default: true
  trilio_endpoint:
    description:
      - Explicit URL override for the Trilio Workload Manager API.
    type: str
  cloud:
    description:
      - Named cloud from C(clouds.yaml) or a dictionary containing cloud configuration.
    type: raw
  auth_type:
    description:
      - Authentication type plugin name (e.g. C(password), C(v3applicationcredential)).
    type: str
  auth:
    description:
      - Dictionary containing Keystone authentication credentials.
    type: dict
  region_name:
    description:
      - OpenStack region name to query.
    type: str
  validate_certs:
    description:
      - Whether to validate SSL/TLS certificates.
    type: bool
    default: true
    aliases: ['verify']
  ca_cert:
    description:
      - Path to CA certificate bundle to verify SSL/TLS connections.
    type: str
    aliases: ['cacert']
  client_cert:
    description:
      - Path to SSL client certificate file.
    type: str
    aliases: ['cert']
  client_key:
    description:
      - Path to SSL client key file.
    type: str
    aliases: ['key']
  interface:
    description:
      - Keystone endpoint interface to discover Trilio services.
    type: str
    default: 'public'
    choices: ['public', 'internal', 'admin']
    aliases: ['endpoint_type']
  timeout:
    description:
      - HTTP request timeout in seconds.
    type: int
    default: 180
  api_timeout:
    description:
      - Timeout in seconds for OpenStack SDK API calls.
    type: int
requirements:
  - "python >= 3.8"
  - "openstacksdk >= 1.0.0"
  - "requests >= 2.25.0"
  - "keystoneauth1 >= 4.0.0"
'''

EXAMPLES = r'''
# Create an NFS Backup Target with DMS (Trilio 6.2+)
- name: Register NFS Backup Target in Trilio
  trilio.trilio_openstack.backup_target:
    cloud: openstack-admin
    state: present
    target_type: nfs
    filesystem_export: "192.168.10.50:/var/nfs/trilio"
    nfs_mount_opts: "nolock,soft,timeo=600,intr,lookupcache=none,nfsvers=3,retrans=10"
    btt_name: "primary-nfs-target"
    is_default: true
  register: nfs_target

# Create an S3 Backup Target using Barbican Secret Reference (Zero Credentials in Git)
- name: Register S3 Backup Target in Trilio
  trilio.trilio_openstack.backup_target:
    cloud: openstack-admin
    state: present
    target_type: s3
    s3_endpoint_url: "https://s3.eu-west-1.amazonaws.com"
    s3_bucket: "company-openstack-backups"
    secret_ref: "https://barbican.cloud.local:9311/v1/secrets/d12d4d98-11a2-4fa8-b0a3-95c52c4238e1"
    btt_name: "s3-immutable-target"
    immutable: true
  register: s3_target

# Remove a Backup Target
- name: Remove Backup Target
  trilio.trilio_openstack.backup_target:
    cloud: openstack-admin
    state: absent
    backup_target_id: "8c58c5f9-9ea0-4781-9c2f-1780926150da"
'''

RETURN = r'''
backup_target:
  description: Detailed information about the created, updated, or discovered backup target.
  returned: always
  type: dict
  contains:
    id:
      description: Backup target UUID.
      type: str
      sample: "7b47b4e8-8db9-4670-8b1e-0679815049cf"
    type:
      description: Storage backend type (nfs or s3).
      type: str
      sample: "nfs"
    filesystem_export:
      description: NFS export path for NFS targets.
      type: str
      sample: "192.168.10.50:/var/nfs/trilio"
    nfs_mount_opts:
      description: NFS mount options string.
      type: str
      sample: "nolock,soft,timeo=600"
    s3_endpoint_url:
      description: S3 endpoint URL for S3 targets.
      type: str
      sample: "https://s3.amazonaws.com"
    s3_bucket:
      description: S3 bucket name.
      type: str
      sample: "trilio-backup-bucket"
    secret_ref:
      description: Barbican secret URL referencing S3 credentials.
      type: str
      sample: "https://barbican:9311/v1/secrets/d12d4d98-11a2-4fa8-b0a3-95c52c4238e1"
    btt_name:
      description: Associated Backup Target Type name.
      type: str
      sample: "primary-nfs-target"
    status:
      description: Backend reachability status reported by DMS (e.g. online, offline).
      type: str
      sample: "online"
    is_default:
      description: Whether the backup target is the default target.
      type: int
      sample: 1
    immutable:
      description: Whether S3 object lock is enabled.
      type: int
      sample: 0
    metadata:
      description: Target metadata key-value pairs.
      type: dict
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.trilio.trilio_openstack.plugins.module_utils.trilio import (
    trilio_argument_spec,
    TrilioClient
)


def run_module():
    module_args = dict(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        target_type=dict(type='str', choices=['nfs', 's3'], aliases=['type']),
        name=dict(type='str'),
        backup_target_id=dict(type='str', aliases=['id']),
        filesystem_export=dict(type='str'),
        nfs_mount_opts=dict(type='str'),
        s3_endpoint_url=dict(type='str'),
        s3_bucket=dict(type='str'),
        secret_ref=dict(type='str'),
        btt_name=dict(type='str'),
        is_default=dict(type='bool', default=False),
        immutable=dict(type='bool', default=False),
        metadata=dict(type='dict'),
        require_dms=dict(type='bool', default=True),
    )

    argument_spec = trilio_argument_spec(**module_args)

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True
    )

    client = TrilioClient(module)

    # 1. Enforce Trilio 6.2+ and Dynamic Mounting Service (DMS) requirement
    require_dms = module.params.get('require_dms', True)
    if require_dms:
        client.validate_dms_support(min_version="6.2")

    state = module.params.get('state', 'present')
    target_type = module.params.get('target_type')
    name = module.params.get('name')
    backup_target_id = module.params.get('backup_target_id')
    filesystem_export = module.params.get('filesystem_export')
    nfs_mount_opts = module.params.get('nfs_mount_opts')
    s3_endpoint_url = module.params.get('s3_endpoint_url')
    s3_bucket = module.params.get('s3_bucket')
    secret_ref = module.params.get('secret_ref')
    btt_name = module.params.get('btt_name') or name or filesystem_export or s3_bucket
    is_default = module.params.get('is_default', False)
    immutable = module.params.get('immutable', False)
    metadata = module.params.get('metadata')

    # 2. Locate existing target if any
    existing_target = None
    if backup_target_id:
        existing_target = client.get_backup_target(backup_target_id)
    else:
        existing_target = client.find_backup_target(
            name=name,
            btt_name=btt_name,
            filesystem_export=filesystem_export,
            s3_endpoint_url=s3_endpoint_url,
            s3_bucket=s3_bucket
        )

    # 3. Handle state=absent
    if state == 'absent':
        if not existing_target:
            module.exit_json(changed=False, msg="Backup target already absent.")
            return

        target_id_to_delete = existing_target.get('id') or backup_target_id
        if module.check_mode:
            module.exit_json(changed=True, msg="Backup target would be deleted.")
            return

        client.delete_backup_target(target_id_to_delete)
        module.exit_json(changed=True, msg="Backup target deleted successfully.")
        return

    # 4. Handle state=present
    if not existing_target:
        # Require target_type when creating new target
        if not target_type:
            module.fail_json(msg="'target_type' ('nfs' or 's3') is required when creating a new backup target.")

        if module.check_mode:
            dummy_target = {
                'id': 'check-mode-dummy-id',
                'type': target_type,
                'filesystem_export': filesystem_export,
                'nfs_mount_opts': nfs_mount_opts,
                's3_endpoint_url': s3_endpoint_url,
                's3_bucket': s3_bucket,
                'secret_ref': secret_ref,
                'btt_name': btt_name,
                'status': 'online',
                'is_default': 1 if is_default else 0,
                'immutable': 1 if immutable else 0,
                'metadata': metadata or {}
            }
            module.exit_json(changed=True, backup_target=dummy_target)
            return

        created_target = client.create_backup_target(
            target_type=target_type,
            filesystem_export=filesystem_export,
            nfs_mount_opts=nfs_mount_opts,
            s3_endpoint_url=s3_endpoint_url,
            s3_bucket=s3_bucket,
            secret_ref=secret_ref,
            btt_name=btt_name,
            is_default=1 if is_default else 0,
            immutable=1 if immutable else 0,
            metadata=metadata
        )

        module.exit_json(changed=True, backup_target=created_target)
        return

    # Target already exists - check if update is needed
    changed = False
    update_kwargs = {}

    if nfs_mount_opts is not None and existing_target.get('nfs_mount_opts') != nfs_mount_opts:
        update_kwargs['nfs_mount_opts'] = nfs_mount_opts
        changed = True

    if secret_ref is not None and existing_target.get('secret_ref') != secret_ref:
        update_kwargs['secret_ref'] = secret_ref
        changed = True

    if metadata is not None and existing_target.get('metadata') != metadata:
        update_kwargs['metadata'] = metadata
        changed = True

    desired_default_val = 1 if is_default else 0
    current_default_val = 1 if (existing_target.get('is_default') in (1, '1', True)) else 0
    if is_default and current_default_val != desired_default_val:
        update_kwargs['is_default'] = desired_default_val
        changed = True

    if changed:
        if module.check_mode:
            module.exit_json(changed=True, backup_target=existing_target)
            return

        target_id = existing_target['id']
        updated_target = client.update_backup_target(target_id, **update_kwargs)
        if is_default and current_default_val != desired_default_val:
            client.set_default_backup_target(target_id)

        module.exit_json(changed=True, backup_target=updated_target or existing_target)
        return

    module.exit_json(changed=False, backup_target=existing_target)


def main():
    run_module()


if __name__ == '__main__':
    main()
