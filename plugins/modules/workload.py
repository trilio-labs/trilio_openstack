#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: workload
short_description: Manage Trilio for OpenStack backup workloads
version_added: "1.1.0"
description:
  - Create, update, and delete Trilio for OpenStack workloads (protection plans).
  - Configures instance membership, backup target types (BTT) in accordance with Trilio 6.2+
    Dynamic Mounting Service (DMS), and automated snapshot schedules.
  - Connects to OpenStack using standard OpenStack connection patterns (clouds.yaml, Keystone auth dictionary,
    or environment variables).
author:
  - Kevin Jackson (@uksysadmin)
options:
  state:
    description:
      - Desired state of the workload.
    type: str
    choices: ['present', 'absent']
    default: 'present'
  name:
    description:
      - Display name of the workload. Required when C(state=present) and creating a new workload.
    type: str
  workload_id:
    description:
      - UUID of an existing workload to update or delete.
    type: str
    aliases: ['id']
  description:
    description:
      - Description of the workload and its purpose.
    type: str
  workload_type:
    description:
      - Workload type name (e.g. C(Parallel) or C(Serial)) or specific UUID.
      - Defaults to the default Parallel workload type if omitted.
    type: str
    aliases: ['workload_type_id']
  instances:
    description:
      - List of OpenStack compute instance (VM) UUIDs or dictionaries with C(id) or C(instance-id) to protect.
    type: list
    elements: raw
    default: []
  backup_target_type:
    description:
      - Name or UUID of the Backup Target Type (BTT) to use as the backup destination.
      - In Trilio 6.2+ with DMS, workloads specify their storage destination via Backup Target Types.
    type: str
    aliases: ['backup_target_types', 'btt']
  jobschedule:
    description:
      - Automated backup schedule and snapshot retention policy dictionary.
      - Sub-keys include C(enabled) (bool), C(interval) (e.g. C(24 hr)), C(start_date) (MM/DD/YYYY),
        C(start_time) (HH:MM AM/PM), C(timezone) (e.g. C(UTC)), C(retention_policy_type) (e.g. C(Number of Snapshots to Keep)),
        C(retention_policy_value) (e.g. C(30)), C(fullbackup_interval) (e.g. C(-1)).
    type: dict
  metadata:
    description:
      - Workload metadata key-value pairs.
    type: dict
  source_platform:
    description:
      - Origin platform for the workload.
    type: str
    default: 'openstack'
  project_id:
    description:
      - OpenStack project (tenant) UUID to create or manage the workload within.
      - Defaults to the authenticated project ID.
    type: str
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
# Create a Trilio workload protecting production web servers
- name: Create Production Web Backup Workload
  trilio.trilio_openstack.workload:
    cloud: openstack
    state: present
    name: "production-web-cluster"
    description: "Daily backup of front-end web server instances"
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
      retention_policy_value: "14"
      fullbackup_interval: "-1"
  register: workload_result

# Delete a workload
- name: Remove decommissioned workload
  trilio.trilio_openstack.workload:
    cloud: openstack
    state: absent
    name: "staging-test-workload"
'''

RETURN = r'''
workload:
  description: Detailed dictionary of the created, updated, or discovered workload.
  returned: always
  type: dict
  contains:
    id:
      description: Workload UUID.
      type: str
      sample: "7b47b4e8-8db9-4670-8b1e-0679815049cf"
    name:
      description: Name of the workload.
      type: str
      sample: "production-web-cluster"
    description:
      description: Description of the workload.
      type: str
      sample: "Daily backup of front-end web server instances"
    status:
      description: Current status (e.g. available, creating, deleting).
      type: str
      sample: "available"
    project_id:
      description: Project ID owning the workload.
      type: str
      sample: "c38ff02cb5794cb4b6e5e8e45f9db1d6"
    workload_type_id:
      description: Workload type UUID.
      type: str
      sample: "272f3105-fhang-4b36-81cf-fb15b8054c25"
    instances:
      description: Protected instance objects.
      type: list
      elements: dict
    jobschedule:
      description: Backup schedule configuration.
      type: dict
    metadata:
      description: Workload metadata key-value pairs.
      type: dict
'''

import re
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.trilio.trilio_openstack.plugins.module_utils.trilio import (
    trilio_argument_spec,
    TrilioClient
)


def _extract_instance_ids(instances):
    """Normalize a list of instances into a sorted set of string UUIDs."""
    ids = set()
    for inst in (instances or []):
        if isinstance(inst, dict):
            iid = inst.get('instance-id') or inst.get('id')
            if iid:
                ids.add(str(iid))
        elif isinstance(inst, str):
            ids.add(str(inst))
    return ids


def run_module():
    module_args = dict(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        name=dict(type='str'),
        workload_id=dict(type='str', aliases=['id']),
        description=dict(type='str'),
        workload_type=dict(type='str', aliases=['workload_type_id']),
        instances=dict(type='list', elements='raw', default=[]),
        backup_target_type=dict(type='str', aliases=['backup_target_types', 'btt']),
        jobschedule=dict(type='dict'),
        metadata=dict(type='dict'),
        source_platform=dict(type='str', default='openstack'),
        project_id=dict(type='str'),
    )

    argument_spec = trilio_argument_spec(**module_args)

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True
    )

    client = TrilioClient(module)

    state = module.params.get('state', 'present')
    name = module.params.get('name')
    workload_id = module.params.get('workload_id')
    description = module.params.get('description')
    workload_type = module.params.get('workload_type')
    instances = module.params.get('instances', [])
    backup_target_type = module.params.get('backup_target_type')
    jobschedule = module.params.get('jobschedule')
    metadata = module.params.get('metadata')
    source_platform = module.params.get('source_platform', 'openstack')
    project_id = module.params.get('project_id')

    # 1. Locate existing workload
    existing_workload = None
    if workload_id:
        existing_workload = client.get_workload(workload_id, project_id=project_id)
    elif name:
        existing_workload = client.get_workload_by_name(name, project_id=project_id)

    # 2. Handle state=absent
    if state == 'absent':
        if not existing_workload:
            module.exit_json(changed=False, msg="Workload already absent.")
            return

        target_wl_id = existing_workload.get('id') or workload_id
        if module.check_mode:
            module.exit_json(changed=True, msg="Workload would be deleted.")
            return

        client.delete_workload(target_wl_id, project_id=project_id)
        module.exit_json(changed=True, msg="Workload deleted successfully.")
        return

    # 3. Handle state=present
    # Resolve Backup Target Type (BTT) name to UUID if provided by name
    btt_id = None
    if backup_target_type:
        is_uuid = bool(re.match(r'^[0-9a-fA-F-]{36}$', backup_target_type))
        if is_uuid:
            btt_id = backup_target_type
        else:
            btt_obj = client.find_backup_target_type(name=backup_target_type)
            if btt_obj:
                btt_id = btt_obj.get('id')
            else:
                # Fall back to passing the string directly (Trilio accepts name or UUID)
                btt_id = backup_target_type

    # Resolve workload_type to UUID if provided by name
    workload_type_id = None
    if workload_type:
        is_uuid = bool(re.match(r'^[0-9a-fA-F-]{36}$', workload_type))
        if is_uuid:
            workload_type_id = workload_type
        else:
            wl_types = client.list_workload_types(project_id=project_id)
            for wt in wl_types:
                if wt.get('name', '').lower() == workload_type.lower():
                    workload_type_id = wt.get('id')
                    break
            if not workload_type_id:
                workload_type_id = workload_type

    if not existing_workload:
        if not name:
            module.fail_json(msg="'name' is required when creating a new workload.")

        if module.check_mode:
            dummy_workload = {
                'id': 'check-mode-dummy-id',
                'name': name,
                'description': description,
                'instances': [{'instance-id': str(i)} for i in _extract_instance_ids(instances)],
                'workload_type_id': workload_type_id or 'type-parallel',
                'backup_target_types': btt_id,
                'jobschedule': jobschedule or {},
                'metadata': metadata or {},
                'status': 'available'
            }
            module.exit_json(changed=True, workload=dummy_workload)
            return

        created_wl = client.create_workload(
            name=name,
            instances=instances,
            workload_type_id=workload_type_id,
            description=description,
            backup_target_types=btt_id,
            jobschedule=jobschedule,
            metadata=metadata,
            source_platform=source_platform,
            project_id=project_id
        )
        module.exit_json(changed=True, workload=created_wl)
        return

    # Workload already exists - check if update is needed
    changed = False
    update_kwargs = {}

    if name and existing_workload.get('name') != name:
        update_kwargs['name'] = name
        changed = True

    if description is not None and existing_workload.get('description') != description:
        update_kwargs['description'] = description
        changed = True

    desired_inst_ids = _extract_instance_ids(instances)
    current_inst_ids = _extract_instance_ids(existing_workload.get('instances', []))
    if instances and desired_inst_ids != current_inst_ids:
        update_kwargs['instances'] = list(desired_inst_ids)
        changed = True

    if jobschedule is not None:
        curr_sched = existing_workload.get('jobschedule') or {}
        # Compare key items in jobschedule
        for k, v in jobschedule.items():
            if curr_sched.get(k) != v:
                update_kwargs['jobschedule'] = jobschedule
                changed = True
                break

    if metadata is not None and existing_workload.get('metadata') != metadata:
        update_kwargs['metadata'] = metadata
        changed = True

    if changed:
        if module.check_mode:
            module.exit_json(changed=True, workload=existing_workload)
            return

        wl_id = existing_workload['id']
        updated_wl = client.update_workload(wl_id, project_id=project_id, **update_kwargs)
        module.exit_json(changed=True, workload=updated_wl or existing_workload)
        return

    module.exit_json(changed=False, workload=existing_workload)


def main():
    run_module()


if __name__ == '__main__':
    main()
