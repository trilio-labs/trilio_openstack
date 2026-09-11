#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: workload_snapshot
short_description: Create and manage snapshots (backups) of Trilio for OpenStack workloads
version_added: "1.1.0"
description:
  - Create on-demand full or incremental snapshots (backups) of a specified Trilio for OpenStack workload.
  - Workload can be targeted by UUID (C(workload_id)) or by display name (C(workload_name) / C(workload)).
  - Supports incremental backup (default) or full backup via C(snapshot_type) or C(full).
  - Designed for end-user project members / tenant application owners to initiate backups of their protected instances.
  - Supports synchronous waiting until the snapshot reaches C(available) status via C(wait).
  - Can remove snapshots using C(state=absent) with C(snapshot_id).
  - Connects to OpenStack using standard OpenStack connection patterns (clouds.yaml, Keystone auth dictionary,
    or environment variables).
notes:
  - "Workload backup execution is an end-user / tenant operation within their assigned OpenStack project."
  - "Incremental snapshots only store changed blocks since the previous snapshot, saving target storage space."
author:
  - Kevin Jackson (@uksysadmin)
options:
  state:
    description:
      - Desired state of the snapshot.
      - C(present) creates a new snapshot / backup of the workload.
      - C(absent) deletes an existing snapshot specified by C(snapshot_id).
    type: str
    choices: ['present', 'absent']
    default: 'present'
  workload:
    description:
      - Name or UUID of the workload to back up.
      - If given a UUID, targets the workload directly.
      - If given a name, resolves the workload UUID dynamically within the OpenStack project.
    type: str
    aliases: ['workload_id', 'id']
  workload_name:
    description:
      - Display name of the workload to back up.
      - Used as an alternative to C(workload) or C(workload_id).
    type: str
  snapshot_id:
    description:
      - UUID of an existing snapshot to delete when C(state=absent).
    type: str
  snapshot_type:
    description:
      - Type of backup to perform.
      - C(incremental) captures changed data blocks since the last snapshot.
      - C(full) captures a complete independent backup of all protected VM volumes and metadata.
    type: str
    choices: ['incremental', 'full']
    default: 'incremental'
    aliases: ['type']
  full:
    description:
      - Boolean flag indicating whether to perform a full backup.
      - If specified, C(true) forces a full backup, and C(false) forces an incremental backup,
        overriding C(snapshot_type).
    type: bool
  name:
    description:
      - Display name for the snapshot.
      - Defaults to Trilio default or C(Snapshot for <workload>) if omitted.
    type: str
    aliases: ['snapshot_name']
  description:
    description:
      - Detailed description for the snapshot.
    type: str
    aliases: ['snapshot_description']
  wait:
    description:
      - Whether to wait synchronously until the snapshot operation completes and reaches C(available) status.
      - If C(false), the module returns immediately after the snapshot task is scheduled with status C(executing).
    type: bool
    default: false
  timeout:
    description:
      - Maximum time in seconds to wait for the snapshot to complete when C(wait=true).
    type: int
    default: 600
  poll_interval:
    description:
      - Number of seconds to pause between polling requests when C(wait=true).
    type: int
    default: 10
  project_id:
    description:
      - OpenStack project (tenant) UUID to manage snapshots within.
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
      - OpenStack region name.
    type: str
  validate_certs:
    description:
      - Validate SSL certificates when connecting over HTTPS.
    type: bool
    aliases: ['verify']
  ca_cert:
    description:
      - Path to custom CA bundle file.
    type: str
    aliases: ['cacert']
  client_cert:
    description:
      - Path to client certificate file for mTLS.
    type: str
    aliases: ['cert']
  client_key:
    description:
      - Path to client private key file for mTLS.
    type: str
    aliases: ['key']
  interface:
    description:
      - Keystone endpoint interface to select from catalog.
    type: str
    choices: ['public', 'internal', 'admin']
    default: 'public'
    aliases: ['endpoint_type']
'''

EXAMPLES = r'''
# Trigger an incremental backup of a workload by name (default)
- name: Create an incremental snapshot of web cluster
  trilio.trilio_openstack.workload_snapshot:
    cloud: openstack
    workload: production-web-cluster
    snapshot_type: incremental
    name: "Nightly Incremental - {{ ansible_date_time.date }}"
    description: "Automated incremental backup"

# Trigger a full backup and wait for completion
- name: Create a full snapshot and wait until available
  trilio.trilio_openstack.workload_snapshot:
    cloud: openstack
    workload: 7b47b4e8-8db9-4670-8b1e-0679815049cf
    snapshot_type: full
    name: "Pre-Upgrade Full Backup"
    description: "Full baseline backup before OS upgrade"
    wait: true
    timeout: 1200

# Delete a snapshot by UUID
- name: Remove an obsolete snapshot
  trilio.trilio_openstack.workload_snapshot:
    cloud: openstack
    state: absent
    snapshot_id: 3c9b7402-45e9-40ea-a059-45e0d7c71d64
'''

RETURN = r'''
snapshot:
  description: Dictionary containing the snapshot details returned by Trilio.
  returned: always when state=present
  type: dict
  contains:
    id:
      description: Snapshot UUID.
      type: str
      sample: "d2f5ca3a-96e0-47cb-b467-33671239aa8e"
    name:
      description: Snapshot display name.
      type: str
      sample: "Nightly Incremental - 2026-09-11"
    description:
      description: Description of the snapshot.
      type: str
      sample: "Automated incremental backup"
    workload_id:
      description: UUID of the parent workload.
      type: str
      sample: "7b47b4e8-8db9-4670-8b1e-0679815049cf"
    snapshot_type:
      description: Type of snapshot created (incremental or full).
      type: str
      sample: "incremental"
    status:
      description: Current status of the snapshot (e.g. executing, available, error).
      type: str
      sample: "executing"
    created_at:
      description: Timestamp when the snapshot was initiated.
      type: str
      sample: "2026-09-11T14:00:00.000000"
    size:
      description: Size of the snapshot in bytes.
      type: int
      sample: 1073741824
'''

import re
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.trilio.trilio_openstack.plugins.module_utils.trilio import (
    trilio_argument_spec,
    TrilioClient
)


def run_module():
    module_args = dict(
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        workload=dict(type='str', aliases=['workload_id', 'id']),
        workload_name=dict(type='str'),
        snapshot_id=dict(type='str'),
        snapshot_type=dict(type='str', choices=['incremental', 'full'], default='incremental', aliases=['type']),
        full=dict(type='bool', default=None),
        name=dict(type='str', aliases=['snapshot_name']),
        description=dict(type='str', aliases=['snapshot_description']),
        wait=dict(type='bool', default=False),
        timeout=dict(type='int', default=600),
        poll_interval=dict(type='int', default=10),
        project_id=dict(type='str'),
    )

    spec = trilio_argument_spec(**module_args)

    module = AnsibleModule(
        argument_spec=spec,
        supports_check_mode=True
    )

    state = module.params.get('state')
    workload_param = module.params.get('workload')
    workload_name_param = module.params.get('workload_name')
    snapshot_id = module.params.get('snapshot_id')
    snapshot_type = module.params.get('snapshot_type')
    full_param = module.params.get('full')
    name = module.params.get('name')
    description = module.params.get('description')
    wait = module.params.get('wait')
    timeout = module.params.get('timeout')
    poll_interval = module.params.get('poll_interval')
    project_id = module.params.get('project_id')

    client = TrilioClient(module)

    # -------------------------------------------------------------------------
    # Handle state=absent (Delete Snapshot)
    # -------------------------------------------------------------------------
    if state == 'absent':
        if not snapshot_id:
            module.fail_json(msg="'snapshot_id' is required when state=absent.")
            return

        # Check if snapshot exists
        existing_snap = client.get_snapshot(snapshot_id, project_id=project_id)
        if not existing_snap:
            module.exit_json(changed=False, msg="Snapshot '%s' not found or already absent." % snapshot_id)
            return

        if module.check_mode:
            module.exit_json(changed=True, msg="Snapshot '%s' would be deleted." % snapshot_id)
            return

        client.delete_snapshot(snapshot_id, project_id=project_id)
        module.exit_json(changed=True, msg="Snapshot '%s' deleted successfully." % snapshot_id)
        return

    # -------------------------------------------------------------------------
    # Handle state=present (Create Snapshot / Backup)
    # -------------------------------------------------------------------------
    # Determine target workload
    target_workload = None
    target_workload_id = None
    workload_identifier = workload_param or workload_name_param

    if not workload_identifier:
        module.fail_json(msg="Either 'workload', 'workload_id', or 'workload_name' must be specified.")
        return

    is_uuid = bool(re.match(r'^[0-9a-fA-F-]{36}$', workload_identifier) or re.match(r'^[0-9a-fA-F]{32}$', workload_identifier))

    if is_uuid and not workload_name_param:
        target_workload_id = workload_identifier
        target_workload = client.get_workload(target_workload_id, project_id=project_id)
        if not target_workload:
            module.fail_json(msg="Workload with UUID '%s' not found." % target_workload_id)
            return
    else:
        search_name = workload_name_param or workload_identifier
        target_workload = client.get_workload_by_name(search_name, project_id=project_id)
        if not target_workload:
            module.fail_json(msg="Workload with name '%s' not found." % search_name)
            return
        target_workload_id = target_workload.get('id')

    # Determine full vs incremental
    if full_param is not None:
        is_full = bool(full_param)
    else:
        is_full = (str(snapshot_type).lower() == 'full')

    snap_name = name
    if not snap_name:
        wl_name = target_workload.get('name') if isinstance(target_workload, dict) else target_workload_id
        snap_type_label = "Full" if is_full else "Incremental"
        snap_name = "%s - %s Backup" % (wl_name, snap_type_label)

    # Check mode
    if module.check_mode:
        dummy_snapshot = {
            'id': 'check-mode-dummy-snapshot-id',
            'name': snap_name,
            'description': description or 'Check mode snapshot',
            'workload_id': target_workload_id,
            'snapshot_type': 'full' if is_full else 'incremental',
            'status': 'available' if wait else 'executing'
        }
        module.exit_json(changed=True, snapshot=dummy_snapshot)
        return

    # Create the snapshot
    created_snap = client.create_snapshot(
        workload_id=target_workload_id,
        name=snap_name,
        description=description,
        full=is_full,
        project_id=project_id
    )

    if not created_snap or not isinstance(created_snap, dict):
        module.fail_json(msg="Failed to create snapshot for workload '%s'." % target_workload_id)
        return

    snap_id = created_snap.get('id')

    # If synchronous wait requested
    if wait and snap_id:
        final_snap = client.wait_for_snapshot(
            snapshot_id=snap_id,
            target_status='available',
            timeout=timeout,
            poll_interval=poll_interval,
            project_id=project_id
        )
        module.exit_json(changed=True, snapshot=final_snap)
        return

    module.exit_json(changed=True, snapshot=created_snap)


def main():
    run_module()


if __name__ == '__main__':
    main()
