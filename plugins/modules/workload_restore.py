#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: workload_restore
short_description: Perform and manage restores from Trilio for OpenStack snapshots
version_added: "1.1.0"
description:
  - Restore workloads or instances from snapshots in Trilio for OpenStack.
  - Supports three distinct restore options.
  - "B(One-Click Restore) (C(oneclick) / C(one-click)): Automated full workload recovery to the original
    configuration and location. Automatically maps instances, networks, and storage."
  - "B(In-Place Restore) (C(inplace) / C(in-place)): Overwrites existing VM volume and boot disk data
    without provisioning new instances. Useful for rapid rollback of corrupted data."
  - "B(Selective Restore) (C(selective)): Granular recovery allowing selection of specific instances,
    renaming instances, custom network and subnet mappings, volume type conversions, flavor changes,
    availability zone assignment, and Nova server group preservation."
  - Snapshots can be targeted directly by UUID (C(snapshot_id) / C(snapshot)), by display name
    (C(snapshot_name)), or by parent workload (C(workload) / C(workload_id)) targeting the latest available backup.
  - Supports loading external Trilio CLI C(restore.json) template files via C(restore_file).
  - Can wait synchronously until the restore reaches C(available) status via C(wait).
  - Can delete existing restore records using C(state=absent) or cancel ongoing restores via C(state=cancelled).
author:
  - Kevin Jackson (@uksysadmin)
options:
  state:
    description:
      - Desired state of the restore job.
      - C(present) initiates a new restore from the targeted snapshot.
      - C(absent) deletes an existing restore record specified by C(restore_id).
      - C(cancelled) cancels an in-progress restore job specified by C(restore_id).
    type: str
    choices: ['present', 'absent', 'cancelled']
    default: 'present'
  restore_type:
    description:
      - Type of restore operation to execute.
      - "C(oneclick) / C(one-click): Complete automated restore to original configuration."
      - "C(inplace) / C(in-place): Overwrite existing compute volume data in-place."
      - "C(selective): Granular restoration with custom network, compute, and volume mappings."
    type: str
    choices: ['oneclick', 'one-click', 'inplace', 'in-place', 'selective']
    default: 'oneclick'
  snapshot:
    description:
      - Name or UUID of the snapshot to restore from.
      - Set to C(latest) in conjunction with C(workload) to target the most recent available snapshot.
    type: str
    aliases: ['snapshot_id', 'id']
  snapshot_name:
    description:
      - Display name of the snapshot to restore from.
    type: str
  workload:
    description:
      - Name or UUID of the parent workload.
      - Used to resolve the target snapshot if C(snapshot) is omitted or set to C(latest).
    type: str
    aliases: ['workload_id']
  workload_name:
    description:
      - Display name of the parent workload.
    type: str
  restore_id:
    description:
      - UUID of an existing restore job.
      - Required when C(state=absent) or C(state=cancelled).
    type: str
  name:
    description:
      - Display name for the restore operation.
      - If omitted, defaults to a descriptive name based on the restore type.
    type: str
    aliases: ['restore_name']
  description:
    description:
      - Detailed description for the restore operation.
    type: str
    aliases: ['restore_description']
  instances:
    description:
      - List of instance configurations for In-Place or Selective restores.
      - For C(inplace) restores, each instance dict supports C(id) (original instance UUID),
        C(include) (bool, default true), C(restore_boot_disk) (bool, default true), and
        C(vdisks) (list of dicts containing C(id) and C(restore_cinder_volume)).
      - For C(selective) restores, each instance dict supports C(id) (original instance UUID),
        C(name) (new display name), C(include) (bool), C(availability_zone), C(server_group) (existing Nova server group UUID),
        C(flavor) (dict of CPU/RAM/disk), C(nics) (network/port mappings), and C(vdisks) (volume type/AZ mappings).
    type: list
    elements: dict
  restore_topology:
    description:
      - Whether to restore the network topology (routers, networks, subnets) in a selective restore.
    type: bool
    default: false
  networks_mapping:
    description:
      - Network mapping rules for selective restores, mapping snapshot networks and subnets to target networks and subnets.
    type: dict
  options:
    description:
      - Direct dictionary override for the Trilio restore options payload.
      - Overrides or augments built-in options.
    type: dict
    aliases: ['restore_options']
  restore_file:
    description:
      - Path to a local JSON file containing restore parameters (standard Trilio CLI C(restore.json) format).
      - If provided, file contents are loaded and merged into the restore options.
    type: path
  wait:
    description:
      - Whether to wait synchronously until the restore operation completes and reaches C(available) status.
      - If C(false), returns immediately after the restore task is queued with status C(restoring).
    type: bool
    default: false
  timeout:
    description:
      - Maximum time in seconds to wait for the restore to complete when C(wait=true).
    type: int
    default: 1200
  poll_interval:
    description:
      - Number of seconds to pause between polling requests when C(wait=true).
    type: int
    default: 10
  project_id:
    description:
      - OpenStack project (tenant) UUID to perform the restore in.
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
# 1. One-Click Restore of the latest snapshot of a workload
- name: Perform one-click restore of web cluster
  trilio.trilio_openstack.workload_restore:
    cloud: openstack
    workload: production-web-cluster
    restore_type: one-click
    name: "Emergency One-Click Rollback"
    wait: true
    timeout: 1800

# 2. In-Place Restore overwriting compute volumes from a specific snapshot
- name: Revert database volumes in-place
  trilio.trilio_openstack.workload_restore:
    cloud: openstack
    snapshot: "b41ad720-449e-4e67-9bf4-1d3820f1245a"
    restore_type: in-place
    name: "DB Corrupted Data Rollback"
    instances:
      - id: "46d8c0b5-7798-4c28-9844-3d0cfcf6bb3e"
        restore_boot_disk: true
        include: true
        vdisks:
          - id: "e63a18a5-d5bb-41bc-b271-9b19e99c8f07"
            restore_cinder_volume: true
    wait: true

# 3. Selective Restore with instance renaming and network mapping
- name: Restore selected instance with new network and flavor
  trilio.trilio_openstack.workload_restore:
    cloud: openstack
    snapshot: "b41ad720-449e-4e67-9bf4-1d3820f1245a"
    restore_type: selective
    name: "Staging Environment Clone"
    restore_topology: false
    instances:
      - id: "46d8c0b5-7798-4c28-9844-3d0cfcf6bb3e"
        name: "web-server-staging-01"
        include: true
        availability_zone: "nova"
    networks_mapping:
      networks:
        - snapshot_network:
            id: "5fb7027d-a2ac-4a21-9ee1-438c281d2b26"
            subnet:
              id: "b7b54304-aa82-4d50-91e6-66445ab56db4"
          target_network:
            id: "2a3b4c5d-6e7f-8a9b-0c1d-2e3f4a5b6c7d"
            name: "staging-network"
            subnet:
              id: "8f7e6d5c-4b3a-2c1d-0e9f-8a7b6c5d4e3f"
    wait: true

# 4. Restore using an existing Trilio restore.json configuration file
- name: Restore using CLI restore.json template
  trilio.trilio_openstack.workload_restore:
    cloud: openstack
    snapshot: "b41ad720-449e-4e67-9bf4-1d3820f1245a"
    restore_file: "/etc/trilio/templates/restore.json"
    wait: true

# 5. Cancel an in-progress restore
- name: Cancel long-running restore job
  trilio.trilio_openstack.workload_restore:
    cloud: openstack
    state: cancelled
    restore_id: "29fdc1f8-1d53-4a10-bb45-e539a64cdbfc"

# 6. Delete a completed restore record
- name: Delete restore record from history
  trilio.trilio_openstack.workload_restore:
    cloud: openstack
    state: absent
    restore_id: "29fdc1f8-1d53-4a10-bb45-e539a64cdbfc"
'''

RETURN = r'''
restore:
  description: Dictionary containing the restore details returned by Trilio.
  returned: always when state=present
  type: dict
  contains:
    id:
      description: Restore job UUID.
      type: str
      sample: "29fdc1f8-1d53-4a10-bb45-e539a64cdbfc"
    name:
      description: Restore job display name.
      type: str
      sample: "OneClick Restore"
    description:
      description: Description of the restore job.
      type: str
      sample: "Automated rollback"
    snapshot_id:
      description: UUID of the snapshot restored from.
      type: str
      sample: "2e56d167-bad7-43c7-8ede-a613c3fe7844"
    status:
      description: Current status of the restore (e.g. restoring, available, error, cancelled).
      type: str
      sample: "available"
    restore_type:
      description: Internal restore type classification.
      type: str
      sample: "restore"
    restore_options:
      description: Detailed options passed to the restore engine.
      type: dict
    created_at:
      description: Timestamp when the restore was initiated.
      type: str
      sample: "2026-09-17T12:00:00.000000"
    finished_at:
      description: Timestamp when the restore completed.
      type: str
      sample: "2026-09-17T12:10:00.000000"
    progress_percent:
      description: Percentage of restore progress.
      type: int
      sample: 100
'''

import json
import os
import re
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.trilio.trilio_openstack.plugins.module_utils.trilio import (
    trilio_argument_spec,
    TrilioClient
)


def normalize_restore_type(r_type):
    """Normalize restore type strings (e.g. 'one-click' -> 'oneclick')."""
    cleaned = (r_type or 'oneclick').lower().replace('-', '').replace('_', '')
    if cleaned in ('oneclick', 'one'):
        return 'oneclick'
    elif cleaned in ('inplace',):
        return 'inplace'
    elif cleaned in ('selective',):
        return 'selective'
    return cleaned


def run_module():
    module_args = dict(
        state=dict(type='str', choices=['present', 'absent', 'cancelled'], default='present'),
        restore_type=dict(type='str', choices=['oneclick', 'one-click', 'inplace', 'in-place', 'selective'], default='oneclick'),
        snapshot=dict(type='str', aliases=['snapshot_id', 'id']),
        snapshot_name=dict(type='str'),
        workload=dict(type='str', aliases=['workload_id']),
        workload_name=dict(type='str'),
        restore_id=dict(type='str'),
        name=dict(type='str', aliases=['restore_name']),
        description=dict(type='str', aliases=['restore_description']),
        instances=dict(type='list', elements='dict'),
        restore_topology=dict(type='bool', default=False),
        networks_mapping=dict(type='dict'),
        options=dict(type='dict', aliases=['restore_options']),
        restore_file=dict(type='path'),
        wait=dict(type='bool', default=False),
        timeout=dict(type='int', default=1200),
        poll_interval=dict(type='int', default=10),
        project_id=dict(type='str'),
    )

    spec = trilio_argument_spec(**module_args)

    module = AnsibleModule(
        argument_spec=spec,
        supports_check_mode=True
    )

    state = module.params.get('state')
    raw_restore_type = module.params.get('restore_type')
    snapshot_param = module.params.get('snapshot')
    snapshot_name_param = module.params.get('snapshot_name')
    workload_param = module.params.get('workload')
    workload_name_param = module.params.get('workload_name')
    restore_id = module.params.get('restore_id')
    name = module.params.get('name')
    description = module.params.get('description')
    instances_param = module.params.get('instances')
    restore_topology = module.params.get('restore_topology')
    networks_mapping = module.params.get('networks_mapping')
    options_param = module.params.get('options')
    restore_file = module.params.get('restore_file')
    wait = module.params.get('wait')
    timeout = module.params.get('timeout')
    poll_interval = module.params.get('poll_interval')
    project_id = module.params.get('project_id')

    client = TrilioClient(module)
    norm_restore_type = normalize_restore_type(raw_restore_type)

    # -------------------------------------------------------------------------
    # Handle state=absent (Delete Restore Record)
    # -------------------------------------------------------------------------
    if state == 'absent':
        if not restore_id:
            module.fail_json(msg="'restore_id' is required when state=absent.")
            return

        existing_restore = client.get_restore(restore_id, project_id=project_id)
        if not existing_restore:
            module.exit_json(changed=False, msg="Restore '%s' not found or already absent." % restore_id)
            return

        if module.check_mode:
            module.exit_json(changed=True, msg="Restore '%s' would be deleted." % restore_id)
            return

        client.delete_restore(restore_id, project_id=project_id)
        module.exit_json(changed=True, msg="Restore '%s' deleted successfully." % restore_id)
        return

    # -------------------------------------------------------------------------
    # Handle state=cancelled (Cancel In-Progress Restore)
    # -------------------------------------------------------------------------
    if state == 'cancelled':
        if not restore_id:
            module.fail_json(msg="'restore_id' is required when state=cancelled.")
            return

        existing_restore = client.get_restore(restore_id, project_id=project_id)
        if not existing_restore:
            module.fail_json(msg="Restore '%s' not found." % restore_id)
            return

        current_status = existing_restore.get('status', '').lower()
        if current_status not in ('restoring', 'executing', 'in-progress'):
            module.exit_json(
                changed=False,
                msg="Restore '%s' is in status '%s' and cannot be cancelled." % (restore_id, current_status),
                restore=existing_restore
            )
            return

        if module.check_mode:
            module.exit_json(changed=True, msg="Restore '%s' would be cancelled." % restore_id)
            return

        client.cancel_restore(restore_id, project_id=project_id)
        updated_restore = client.get_restore(restore_id, project_id=project_id)
        module.exit_json(changed=True, msg="Restore '%s' cancel request submitted." % restore_id, restore=updated_restore)
        return

    # -------------------------------------------------------------------------
    # Handle state=present (Trigger / Create Restore)
    # -------------------------------------------------------------------------
    # Resolve target snapshot
    snapshot_identifier = snapshot_param or snapshot_name_param
    workload_identifier = workload_param or workload_name_param

    if not snapshot_identifier and not workload_identifier:
        module.fail_json(msg="Either 'snapshot' ('snapshot_id', 'snapshot_name') or 'workload' ('workload_id', 'workload_name') must be specified.")
        return

    target_snapshot = None
    target_snapshot_id = None

    if not module.check_mode:
        target_snapshot = client.resolve_snapshot(
            snapshot_identifier=snapshot_identifier,
            workload_identifier=workload_identifier,
            project_id=project_id
        )
        if not target_snapshot:
            identifier_desc = snapshot_identifier or ("latest snapshot for workload '%s'" % workload_identifier)
            module.fail_json(msg="Failed to resolve snapshot for '%s'." % identifier_desc)
            return
        target_snapshot_id = target_snapshot.get('id')
    else:
        # In check mode, try to resolve if possible, fallback to dummy
        try:
            target_snapshot = client.resolve_snapshot(
                snapshot_identifier=snapshot_identifier,
                workload_identifier=workload_identifier,
                project_id=project_id
            )
            target_snapshot_id = target_snapshot.get('id') if target_snapshot else 'check-mode-dummy-snapshot-id'
        except Exception:
            target_snapshot_id = snapshot_identifier or 'check-mode-dummy-snapshot-id'

    # Build options payload
    built_options = {}

    # 1. Load from restore_file if specified
    if restore_file:
        if not os.path.isfile(restore_file):
            module.fail_json(msg="Restore file '%s' not found." % restore_file)
            return
        try:
            with open(restore_file, 'r') as rf:
                file_data = json.load(rf)
                if isinstance(file_data, dict):
                    if 'restore' in file_data and isinstance(file_data['restore'], dict):
                        built_options = file_data['restore'].get('options', {})
                        if not name and 'name' in file_data['restore']:
                            name = file_data['restore']['name']
                        if not description and 'description' in file_data['restore']:
                            description = file_data['restore']['description']
                    elif 'options' in file_data and isinstance(file_data['options'], dict):
                        built_options = file_data['options']
                    else:
                        built_options = file_data
        except Exception as e:
            module.fail_json(msg="Failed to parse JSON restore file '%s': %s" % (restore_file, str(e)))
            return

    # 2. Merge options dictionary if provided
    if options_param:
        built_options.update(options_param)

    # 3. Ensure base structure
    if 'type' not in built_options:
        built_options['type'] = 'openstack'
    if 'restore_type' not in built_options:
        built_options['restore_type'] = norm_restore_type
    if 'oneclickrestore' not in built_options:
        built_options['oneclickrestore'] = (norm_restore_type == 'oneclick')
    if 'openstack' not in built_options:
        built_options['openstack'] = {}

    openstack_config = built_options['openstack']

    # 4. Apply restore-type-specific parameters
    if norm_restore_type == 'oneclick':
        # One-click restore requires empty or minimal openstack config
        built_options['oneclickrestore'] = True
        built_options['restore_type'] = 'oneclick'

    elif norm_restore_type == 'inplace':
        built_options['oneclickrestore'] = False
        built_options['restore_type'] = 'inplace'
        if instances_param:
            processed_instances = []
            for inst in instances_param:
                inst_entry = {
                    'id': inst.get('id'),
                    'include': inst.get('include', True),
                    'restore_boot_disk': inst.get('restore_boot_disk', True),
                }
                if 'vdisks' in inst:
                    inst_entry['vdisks'] = inst['vdisks']
                processed_instances.append(inst_entry)
            openstack_config['instances'] = processed_instances

    elif norm_restore_type == 'selective':
        built_options['oneclickrestore'] = False
        built_options['restore_type'] = 'selective'
        if instances_param:
            openstack_config['instances'] = instances_param
        if restore_topology is not None:
            openstack_config['restore_topology'] = bool(restore_topology)
        if networks_mapping:
            openstack_config['networks_mapping'] = networks_mapping

    # Prepare display name and description
    restore_label = 'OneClick' if norm_restore_type == 'oneclick' else ('Inplace' if norm_restore_type == 'inplace' else 'Selective')
    restore_name = name or ("%s Restore" % restore_label)
    restore_desc = description or ("%s restore triggered via Ansible" % restore_label)

    # Check mode
    if module.check_mode:
        dummy_restore = {
            'id': 'check-mode-dummy-restore-id',
            'name': restore_name,
            'description': restore_desc,
            'snapshot_id': target_snapshot_id,
            'restore_type': 'restore',
            'status': 'available' if wait else 'restoring',
            'restore_options': built_options
        }
        module.exit_json(changed=True, restore=dummy_restore)
        return

    # Trigger restore
    created_restore = client.create_restore(
        snapshot_id=target_snapshot_id,
        restore_type=norm_restore_type,
        name=restore_name,
        description=restore_desc,
        options=built_options,
        project_id=project_id
    )

    if not created_restore or not isinstance(created_restore, dict):
        module.fail_json(msg="Failed to initiate restore from snapshot '%s'." % target_snapshot_id)
        return

    created_restore_id = created_restore.get('id')

    # If wait requested
    if wait and created_restore_id:
        final_restore = client.wait_for_restore(
            restore_id=created_restore_id,
            target_status='available',
            timeout=timeout,
            poll_interval=poll_interval,
            project_id=project_id
        )
        module.exit_json(changed=True, restore=final_restore)
        return

    module.exit_json(changed=True, restore=created_restore)


def main():
    run_module()


if __name__ == '__main__':
    main()
