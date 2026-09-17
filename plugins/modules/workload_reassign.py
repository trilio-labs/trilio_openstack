#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: workload_reassign
short_description: Reassign Trilio for OpenStack workloads to a new tenant/user
version_added: "1.1.0"
description:
  - Reassign ownership of one or more Trilio workloads and their associated backup snapshot chains
    from a source OpenStack tenant (project) to a target tenant and user.
  - Enables cross-tenant workload migration, tenant consolidation, and project lifecycle management.
  - Designed for cloud administrators (requires C(admin) role privileges).
  - Automatically resolves project names and user names to OpenStack UUIDs.
author:
  - Kevin Jackson (@uksysadmin)
options:
  workload:
    description:
      - Name or UUID of the workload to reassign.
    type: str
    aliases: ['workload_id', 'id']
  workload_ids:
    description:
      - List of workload names or UUIDs to reassign.
    type: list
    elements: str
  workload_name:
    description:
      - Display name of the workload to reassign.
    type: str
  target_project:
    description:
      - Name or UUID of the destination OpenStack project (tenant) to receive the workload.
    type: str
    required: true
    aliases: ['new_tenant_id', 'target_tenant', 'destination_project', 'destination_tenant']
  target_user:
    description:
      - Name or UUID of the OpenStack user within the destination project who will own the workload.
    type: str
    required: true
    aliases: ['user_id', 'user', 'destination_user']
  source_project:
    description:
      - Name or UUID of the original source OpenStack project (tenant).
    type: str
    aliases: ['old_tenant_id', 'source_tenant', 'old_tenant_ids']
  source_btt:
    description:
      - Name or UUID of the source Backup Target Type (BTT).
    type: raw
    aliases: ['source_btt_id', 'source_backup_target_type']
  target_btt:
    description:
      - Name or UUID of the target Backup Target Type (BTT) in the destination project.
    type: str
    aliases: ['target_btt_id', 'target_backup_target_type']
  migrate_storage:
    description:
      - Whether to physically migrate backup storage data to a new target backend.
    type: bool
    default: false
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
      - Authentication dictionary containing OpenStack credentials.
    type: dict
  region_name:
    description:
      - OpenStack region name to connect to.
    type: str
  interface:
    description:
      - Endpoint interface to discover from Keystone service catalog.
    type: str
    default: 'public'
    choices: ['public', 'internal', 'admin']
  validate_certs:
    description:
      - Whether to validate SSL/TLS certificates.
    type: bool
    default: true
    aliases: ['verify']
  timeout:
    description:
      - HTTP request timeout in seconds.
    type: int
    default: 180
  trilio_endpoint:
    description:
      - Explicit URL override for the Trilio Workload Manager API.
    type: str
'''

EXAMPLES = r'''
# 1. Reassign a workload from one project to another using project and user names
- name: Reassign Fileserver Backup to restore project
  trilio.trilio_openstack.workload_reassign:
    cloud: admin
    workload: "Fileserver Backup"
    target_project: "kevin-restore"
    target_user: "kevin"
    source_btt: "d11516df-be26-4587-aa30-5bd9a4c9c247"

# 2. Reassign multiple workloads by UUID
- name: Reassign multiple workloads to target tenant
  trilio.trilio_openstack.workload_reassign:
    cloud: admin
    workload_ids:
      - "46d8c0b5-7798-4c28-9844-3d0cfcf6bb3e"
      - "7b47b4e8-8db9-4670-8b1e-0679815049cf"
    target_project: "a8f3b0e1-9c2d-4e5f-8a1b-3c5d7e9f0a2b"
    target_user: "f4e2d0c8-1b3a-4f5e-9a7c-8d6b5a4c3e2f"
    source_project: "b9e4a1f2-0d3c-4e5b-8f7a-2c4e6d8a0b1c"

# 3. Reset workload back to original source project
- name: Reassign workload back to original source tenant
  trilio.trilio_openstack.workload_reassign:
    cloud: admin
    workload: "Fileserver Backup"
    target_project: "kevin-demo"
    target_user: "kevin"
'''

RETURN = r'''
workloads:
  description: List or dictionary of reassigned workloads returned by Trilio API.
  returned: always
  type: raw
  sample:
    - id: "46d8c0b5-7798-4c28-9844-3d0cfcf6bb3e"
      name: "Fileserver Backup"
      project_id: "a8f3b0e1-9c2d-4e5f-8a1b-3c5d7e9f0a2b"
      user_id: "f4e2d0c8-1b3a-4f5e-9a7c-8d6b5a4c3e2f"
target_project_id:
  description: Resolved UUID of the target OpenStack project.
  returned: always
  type: str
  sample: "a8f3b0e1-9c2d-4e5f-8a1b-3c5d7e9f0a2b"
target_user_id:
  description: Resolved UUID of the target OpenStack user.
  returned: always
  type: str
  sample: "f4e2d0c8-1b3a-4f5e-9a7c-8d6b5a4c3e2f"
changed:
  description: Whether the workload reassignment was executed.
  returned: always
  type: bool
  sample: true
'''

import re
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.trilio.trilio_openstack.plugins.module_utils.trilio import (
    trilio_argument_spec,
    TrilioClient
)


def run_module():
    argument_spec = trilio_argument_spec(
        workload=dict(type='str', aliases=['workload_id', 'id']),
        workload_ids=dict(type='list', elements='str'),
        workload_name=dict(type='str'),
        target_project=dict(
            type='str',
            required=True,
            aliases=['new_tenant_id', 'target_tenant', 'destination_project', 'destination_tenant']
        ),
        target_user=dict(
            type='str',
            required=True,
            aliases=['user_id', 'user', 'destination_user']
        ),
        source_project=dict(
            type='str',
            aliases=['old_tenant_id', 'source_tenant', 'old_tenant_ids']
        ),
        source_btt=dict(
            type='raw',
            aliases=['source_btt_id', 'source_backup_target_type']
        ),
        target_btt=dict(
            type='str',
            aliases=['target_btt_id', 'target_backup_target_type']
        ),
        migrate_storage=dict(type='bool', default=False),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True
    )

    client = TrilioClient(module)

    # Collect workload identifiers
    raw_workloads = []
    if module.params.get('workload_ids'):
        raw_workloads.extend(module.params.get('workload_ids'))
    if module.params.get('workload'):
        raw_workloads.append(module.params.get('workload'))
    if module.params.get('workload_name'):
        raw_workloads.append(module.params.get('workload_name'))

    # Deduplicate while preserving order
    seen = set()
    workload_identifiers = []
    for w in raw_workloads:
        if w and w not in seen:
            seen.add(w)
            workload_identifiers.append(w)

    if not workload_identifiers:
        module.fail_json(msg="At least one of 'workload', 'workload_ids', or 'workload_name' must be specified.")

    target_project = module.params.get('target_project')
    target_user = module.params.get('target_user')
    source_project = module.params.get('source_project')
    source_btt = module.params.get('source_btt')
    target_btt = module.params.get('target_btt')
    migrate_storage = module.params.get('migrate_storage')

    # Resolve project and user UUIDs
    target_project_id = client.find_project_id(target_project)
    target_user_id = client.find_user_id(target_user)

    # Resolve workload UUIDs and check if already in target project
    resolved_workload_ids = []
    already_assigned_count = 0

    all_wls = client.list_workloads(all_projects=True)
    for identifier in workload_identifiers:
        is_uuid = bool(re.match(r'^[0-9a-fA-F-]{36}$', str(identifier)) or re.match(r'^[0-9a-fA-F]{32}$', str(identifier)))
        found_wl = None
        for w in all_wls:
            if is_uuid and w.get('id') == identifier:
                found_wl = w
                break
            elif not is_uuid and (w.get('name') == identifier or w.get('display_name') == identifier):
                found_wl = w
                break

        if found_wl:
            wl_id = found_wl.get('id')
            resolved_workload_ids.append(wl_id)
            # Check if already owned by target project and target user
            curr_proj = found_wl.get('project_id') or found_wl.get('tenant_id')
            curr_user = found_wl.get('user_id')
            if curr_proj == target_project_id and (not target_user_id or curr_user == target_user_id):
                already_assigned_count += 1
        else:
            resolved_workload_ids.append(identifier)

    # Idempotency check: if all requested workloads are already in the target project/user
    if already_assigned_count == len(resolved_workload_ids) and len(resolved_workload_ids) > 0:
        module.exit_json(
            changed=False,
            msg="All specified workloads are already assigned to target project %s." % target_project_id,
            target_project_id=target_project_id,
            target_user_id=target_user_id,
            workloads=resolved_workload_ids
        )
        return

    if module.check_mode:
        module.exit_json(
            changed=True,
            target_project_id=target_project_id,
            target_user_id=target_user_id,
            workloads=resolved_workload_ids
        )
        return

    # Execute reassignment API call
    res = client.reassign_workloads(
        workload_ids=resolved_workload_ids,
        new_tenant_id=target_project_id,
        user_id=target_user_id,
        old_tenant_ids=[source_project] if source_project else None,
        source_btt=source_btt,
        target_btt=target_btt,
        migrate_storage=migrate_storage
    )

    module.exit_json(
        changed=True,
        target_project_id=target_project_id,
        target_user_id=target_user_id,
        workloads=res or resolved_workload_ids
    )


def main():
    run_module()


if __name__ == '__main__':
    main()
