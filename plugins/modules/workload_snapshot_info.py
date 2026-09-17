#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r"""
---
module: workload_snapshot_info
short_description: Retrieve detailed information and network topology from Trilio for OpenStack workload snapshots
version_added: "1.0.1"
description:
  - Retrieve detailed information, instances, and network topology from snapshots of Trilio for OpenStack workloads.
  - Useful for inspecting which instances and networks (with subnets and CIDRs) are contained in a backup before restoring.
  - Automatically extracts discovered networks, subnets, routers, and instances to enable precise lifecycle management and teardown.
author:
  - Kevin Jackson (@uksysadmin)
options:
  workload:
    description:
      - Name or UUID of the parent workload.
    type: str
    aliases: ['workload_id', 'workload_name']
  snapshot:
    description:
      - Name or UUID of the snapshot to query.
      - Set to C(latest) to automatically target the most recent available snapshot of the workload.
    type: str
    aliases: ['snapshot_id', 'snapshot_name', 'id']
  all_snapshots:
    description:
      - When true, retrieves all snapshots for the workload.
    type: bool
    default: false
  project_id:
    description:
      - OpenStack project (tenant) UUID to query snapshots within.
    type: str
  trilio_endpoint:
    description:
      - Optional explicit URL for Trilio Workload Manager API.
    type: str
  cloud:
    description:
      - Named cloud from C(clouds.yaml) or a dictionary containing cloud configuration.
    type: raw
  auth:
    description:
      - Dictionary containing Keystone authentication credentials.
    type: dict
  auth_type:
    description:
      - Authentication type plugin name (e.g. C(password), C(v3applicationcredential)).
    type: str
  region_name:
    description:
      - OpenStack region name to query.
    type: str
  validate_certs:
    description:
      - Whether to validate SSL/TLS certificates.
    type: bool
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
"""

EXAMPLES = r"""
- name: Query latest snapshot and discovered network topology for a workload
  trilio.trilio_openstack.workload_snapshot_info:
    workload: "Fileserver Workloads"
    snapshot: "latest"
  register: snapshot_details

- name: Display discovered networks in snapshot
  ansible.builtin.debug:
    msg:
      - "Instances: {{ snapshot_details.discovered_instances }}"
      - "Networks:  {{ snapshot_details.discovered_networks }}"
      - "Topology:  {{ snapshot_details.discovered_topology }}"
"""

RETURN = r"""
snapshots:
  description: List of detailed snapshot records.
  returned: always
  type: list
  elements: dict
discovered_instances:
  description: List of instance (VM) names protected in the snapshot.
  returned: always
  type: list
  elements: str
discovered_networks:
  description: List of network names associated with instances in the snapshot.
  returned: always
  type: list
  elements: str
discovered_topology:
  description: Detailed network topology mapping networks to subnets and IP configurations.
  returned: always
  type: list
  elements: dict
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.trilio.trilio_openstack.plugins.module_utils.trilio import (
    trilio_argument_spec,
    TrilioClient
)


def run_module():
    module_args = dict(
        workload=dict(type='str', aliases=['workload_id', 'workload_name']),
        snapshot=dict(type='str', aliases=['snapshot_id', 'snapshot_name', 'id']),
        all_snapshots=dict(type='bool', default=False),
        project_id=dict(type='str'),
    )

    argument_spec = trilio_argument_spec(**module_args)

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True
    )

    client = TrilioClient(module)

    workload_identifier = module.params.get('workload')
    snapshot_identifier = module.params.get('snapshot')
    all_snapshots = module.params.get('all_snapshots', False)
    project_id = module.params.get('project_id')

    resolved_workload_id = None
    if workload_identifier:
        found_wl = client.get_workload_by_name(workload_identifier, project_id=project_id)
        if found_wl:
            resolved_workload_id = found_wl.get('id')
        else:
            resolved_workload_id = workload_identifier

    raw_snapshots = []
    if all_snapshots or (resolved_workload_id and not snapshot_identifier):
        raw_snapshots = client.list_snapshots(workload_id=resolved_workload_id, project_id=project_id)
    elif snapshot_identifier or resolved_workload_id:
        target_snap = client.resolve_snapshot(
            snapshot_identifier=snapshot_identifier,
            workload_identifier=resolved_workload_id,
            project_id=project_id
        )
        if target_snap:
            raw_snapshots = [target_snap]

    detailed_snapshots = []
    discovered_instances = set()
    discovered_networks_map = {}

    for s in raw_snapshots:
        s_id = s.get('id') if isinstance(s, dict) else s
        if not s_id:
            continue
        det = client.get_snapshot(s_id, project_id=project_id)
        if not det or not isinstance(det, dict):
            det = s
        detailed_snapshots.append(det)

        for inst in det.get('instances', []):
            if inst.get('name'):
                discovered_instances.add(inst.get('name'))
            for nic in inst.get('nics', []):
                net = nic.get('network', {})
                subnet = net.get('subnet', {})
                net_name = net.get('name')
                net_id = net.get('id')
                if net_name:
                    if net_name not in discovered_networks_map:
                        discovered_networks_map[net_name] = {
                            'id': net_id,
                            'name': net_name,
                            'subnets': []
                        }
                    if subnet and subnet.get('name'):
                        sub_name = subnet.get('name')
                        sub_id = subnet.get('id')
                        sub_cidr = subnet.get('cidr')
                        existing_sub_names = [sub['name'] for sub in discovered_networks_map[net_name]['subnets']]
                        if sub_name not in existing_sub_names:
                            discovered_networks_map[net_name]['subnets'].append({
                                'id': sub_id,
                                'name': sub_name,
                                'cidr': sub_cidr
                            })

    module.exit_json(
        changed=False,
        snapshots=detailed_snapshots,
        discovered_instances=sorted(list(discovered_instances)),
        discovered_networks=sorted(list(discovered_networks_map.keys())),
        discovered_topology=list(discovered_networks_map.values())
    )


def main():
    run_module()


if __name__ == '__main__':
    main()
