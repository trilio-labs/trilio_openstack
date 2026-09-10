#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: workload_info
short_description: Retrieve information about Trilio for OpenStack workloads
version_added: "1.0.0"
description:
  - Retrieve information about one or more workloads from Trilio for OpenStack (Workload Manager).
  - Authenticates to OpenStack Keystone using standard OpenStack connection patterns,
    seamlessly complementing existing C(openstack.cloud) modules.
author:
  - Kevin Jackson (@uksysadmin)
options:
  name:
    description:
      - Name or glob pattern to filter workloads.
    type: str
  workload_id:
    description:
      - Specific UUID of the workload to retrieve.
    type: str
    aliases: ['id']
  all_projects:
    description:
      - Whether to list workloads across all projects.
      - Requires OpenStack administrator privileges.
    type: bool
    default: false
  project_id:
    description:
      - OpenStack project (tenant) UUID to query workloads for.
      - Defaults to the authenticated project ID.
    type: str
  detailed:
    description:
      - When true, retrieves full workload details (including instance members, job schedule, and storage target).
    type: bool
    default: true
  nfs_share:
    description:
      - Optional backup target NFS share path to filter workloads by.
    type: str
  trilio_endpoint:
    description:
      - Optional explicit URL for the Trilio Workload Manager API (wlm-api).
      - If omitted, the endpoint is automatically discovered from the Keystone service catalog.
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
      - How long to wait in seconds for API responses.
    type: int
    default: 180
  api_timeout:
    description:
      - Timeout in seconds for OpenStack SDK API calls.
    type: int
'''

EXAMPLES = r'''
# List all workloads in the project defined in clouds.yaml
- name: List workloads using clouds.yaml
  trilio.trilio_openstack.workload_info:
    cloud: openstack
  register: result

- name: Display workloads found
  ansible.builtin.debug:
    var: result.workloads

# Filter workload by name
- name: Find specific workload by name
  trilio.trilio_openstack.workload_info:
    cloud: production
    name: "db-cluster-backup"
  register: db_workload

# Retrieve a specific workload by UUID
- name: Get workload by UUID
  trilio.trilio_openstack.workload_info:
    cloud: openstack
    workload_id: "7b47b4e8-8db9-4670-8b1e-0679815049cf"

# List workloads across all projects as OpenStack Admin
- name: List all workloads across all tenants
  trilio.trilio_openstack.workload_info:
    cloud: openstack-admin
    all_projects: true
  register: all_workloads

# Authenticate using Keystone Application Credentials without storing credentials in playbooks
- name: Authenticate via Application Credentials
  trilio.trilio_openstack.workload_info:
    auth_type: v3applicationcredential
    auth:
      auth_url: "{{ lookup('ansible.builtin.env', 'OS_AUTH_URL') }}"
      application_credential_id: "{{ lookup('ansible.builtin.env', 'OS_APPLICATION_CREDENTIAL_ID') }}"
      application_credential_secret: "{{ lookup('ansible.builtin.env', 'OS_APPLICATION_CREDENTIAL_SECRET') }}"
  register: app_cred_workloads
'''

RETURN = r'''
workloads:
  description: List of workloads matching the query criteria.
  returned: always
  type: list
  elements: dict
  contains:
    id:
      description: Workload UUID.
      type: str
      sample: "7b47b4e8-8db9-4670-8b1e-0679815049cf"
    name:
      description: Name of the workload.
      type: str
      sample: "production-web-servers"
    description:
      description: Description of the workload.
      type: str
      sample: "Daily backup of front-end VM cluster"
    status:
      description: Current status of the workload (e.g. available, creating, deleting, error).
      type: str
      sample: "available"
    project_id:
      description: OpenStack project/tenant ID owning this workload.
      type: str
      sample: "c38ff02cb5794cb4b6e5e8e45f9db1d6"
    user_id:
      description: OpenStack Keystone user ID that created the workload.
      type: str
      sample: "3c368d4078bd44a0bdf5dbceeeebef31"
    workload_type_id:
      description: Workload type UUID (Serial or Parallel).
      type: str
      sample: "272f3105-fhang-4b36-81cf-fb15b8054c25"
    storage_url:
      description: Backup target storage URL (e.g. NFS share path or S3 target).
      type: str
      sample: "192.168.10.50:/var/nfs/trilio"
    instances:
      description: List of OpenStack instances (VMs) protected by this workload.
      type: list
      elements: dict
      sample:
        - id: "28e08d66-8968-45e0-9bc7-5bb83fc44007"
          name: "web-server-01"
    jobschedule:
      description: Workload backup schedule configuration.
      type: dict
      sample:
        enabled: true
        interval: "24 hr"
        retention_policy_type: "Number of Snapshots to Keep"
        retention_policy_value: "30"
        fullbackup_interval: "-1"
        timezone: "UTC"
    metadata:
      description: Workload metadata key-value pairs.
      type: dict
    created_at:
      description: Workload creation timestamp.
      type: str
      sample: "2026-09-01T08:30:00.000000"
    updated_at:
      description: Workload last update timestamp.
      type: str
      sample: "2026-09-10T02:00:00.000000"
'''

import fnmatch
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.trilio.trilio_openstack.plugins.module_utils.trilio import (
    trilio_argument_spec,
    TrilioClient
)


def run_module():
    module_args = dict(
        name=dict(type='str'),
        workload_id=dict(type='str', aliases=['id']),
        all_projects=dict(type='bool', default=False),
        project_id=dict(type='str'),
        detailed=dict(type='bool', default=True),
        nfs_share=dict(type='str'),
    )

    argument_spec = trilio_argument_spec(**module_args)

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True
    )

    client = TrilioClient(module)

    workload_id = module.params.get('workload_id')
    name = module.params.get('name')
    all_projects = module.params.get('all_projects', False)
    project_id = module.params.get('project_id')
    detailed = module.params.get('detailed', True)
    nfs_share = module.params.get('nfs_share')

    workloads = []

    if workload_id:
        workload = client.get_workload(workload_id, project_id=project_id)
        if workload:
            workloads = [workload]
    else:
        raw_workloads = client.list_workloads(
            project_id=project_id,
            all_projects=all_projects,
            detailed=detailed,
            nfs_share=nfs_share
        )

        if name:
            filtered = []
            for wl in raw_workloads:
                wl_name = wl.get('name', '')
                if wl_name == name or fnmatch.fnmatch(wl_name, name):
                    filtered.append(wl)
            workloads = filtered
        else:
            workloads = raw_workloads

    module.exit_json(changed=False, workloads=workloads)


def main():
    run_module()


if __name__ == '__main__':
    main()
