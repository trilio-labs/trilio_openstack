#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: backup_target_info
short_description: Retrieve information about Trilio for OpenStack backup targets and target types
version_added: "1.1.0"
description:
  - Retrieve details, reachability status, and configuration of Trilio Backup Targets (NFS and S3)
    and Backup Target Types (BTT) managed via Dynamic Mounting Service (DMS).
  - Requires Trilio version 6.2 or newer with DMS support.
author:
  - Kevin Jackson (@uksysadmin)
options:
  backup_target_id:
    description:
      - Specific UUID of a backup target to query.
    type: str
    aliases: ['id']
  name:
    description:
      - Filter backup targets by name or BTT name.
    type: str
  target_type:
    description:
      - Filter backup targets by storage type (C(nfs) or C(s3)).
    type: str
    choices: ['nfs', 's3']
    aliases: ['type']
  include_target_types:
    description:
      - Whether to also query and return the list of configured Backup Target Types (BTT).
    type: bool
    default: true
  require_dms:
    description:
      - Enforce verification that the Trilio API supports DMS (Trilio 6.2+).
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
# List all backup targets and their DMS reachability status
- name: Query all backup targets
  trilio.trilio_openstack.backup_target_info:
    cloud: openstack-admin
  register: result

- name: Display discovered targets
  ansible.builtin.debug:
    msg: "Target {{ item.btt_name }} ({{ item.id }}) status: {{ item.status }}"
  loop: "{{ result.backup_targets }}"

# Filter for S3 backup targets only
- name: Query S3 backup targets
  trilio.trilio_openstack.backup_target_info:
    cloud: openstack-admin
    target_type: s3
  register: s3_targets
'''

RETURN = r'''
backup_targets:
  description: List of discovered backup targets matching query criteria.
  returned: always
  type: list
  elements: dict
  contains:
    id:
      description: Backup target UUID.
      type: str
      sample: "7b47b4e8-8db9-4670-8b1e-0679815049cf"
    type:
      description: Target type (nfs or s3).
      type: str
      sample: "nfs"
    filesystem_export:
      description: NFS filesystem export path.
      type: str
      sample: "192.168.10.50:/var/nfs/trilio"
    nfs_mount_opts:
      description: NFS mount options string.
      type: str
      sample: "nolock,soft,timeo=600"
    s3_endpoint_url:
      description: S3 endpoint URL.
      type: str
      sample: "https://s3.amazonaws.com"
    s3_bucket:
      description: S3 bucket name.
      type: str
      sample: "prod-backups"
    secret_ref:
      description: Barbican secret URL referencing credentials.
      type: str
      sample: "https://barbican:9311/v1/secrets/d12d4d98-11a2-4fa8-b0a3-95c52c4238e1"
    btt_name:
      description: Associated Backup Target Type name.
      type: str
      sample: "primary-nfs"
    status:
      description: Backend reachability reported by DMS (e.g. online, offline).
      type: str
      sample: "online"
    is_default:
      description: Whether this is the default backup target.
      type: int
      sample: 1
    immutable:
      description: Whether S3 object lock is enabled.
      type: int
      sample: 0
    metadata:
      description: Target metadata key-value pairs.
      type: dict
backup_target_types:
  description: List of discovered Backup Target Types (BTT).
  returned: when include_target_types is true
  type: list
  elements: dict
  contains:
    id:
      description: Backup Target Type UUID.
      type: str
      sample: "fdae1b10-9852-4c68-8879-64ead0aed31b"
    name:
      description: Backup Target Type name.
      type: str
      sample: "primary-nfs"
    backup_targets_id:
      description: Associated Backup Target UUID.
      type: str
      sample: "7b47b4e8-8db9-4670-8b1e-0679815049cf"
    is_public:
      description: Whether this target type is accessible to all projects.
      type: bool
      sample: true
'''

import fnmatch
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.trilio.trilio_openstack.plugins.module_utils.trilio import (
    trilio_argument_spec,
    TrilioClient
)


def run_module():
    module_args = dict(
        backup_target_id=dict(type='str', aliases=['id']),
        name=dict(type='str'),
        target_type=dict(type='str', choices=['nfs', 's3'], aliases=['type']),
        include_target_types=dict(type='bool', default=True),
        require_dms=dict(type='bool', default=True),
    )

    argument_spec = trilio_argument_spec(**module_args)

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True
    )

    client = TrilioClient(module)

    require_dms = module.params.get('require_dms', True)
    if require_dms:
        client.validate_dms_support(min_version="6.2")

    backup_target_id = module.params.get('backup_target_id')
    name = module.params.get('name')
    target_type = module.params.get('target_type')
    include_target_types = module.params.get('include_target_types', True)

    targets = []
    if backup_target_id:
        bt = client.get_backup_target(backup_target_id)
        if bt:
            targets = [bt]
    else:
        raw_targets = client.list_backup_targets()
        filtered = []
        for bt in raw_targets:
            if target_type and bt.get('type') != target_type:
                continue
            if name:
                bt_name = bt.get('name') or bt.get('btt_name') or ''
                if bt_name != name and not fnmatch.fnmatch(bt_name, name):
                    continue
            filtered.append(bt)
        targets = filtered

    target_types = []
    if include_target_types:
        target_types = client.list_backup_target_types()

    module.exit_json(
        changed=False,
        backup_targets=targets,
        backup_target_types=target_types
    )


def main():
    run_module()


if __name__ == '__main__':
    main()
