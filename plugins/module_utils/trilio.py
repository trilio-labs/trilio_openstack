# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

"""
Shared module_utils for Trilio for OpenStack Ansible Collection.
Provides Keystone authentication integration, service catalog endpoint discovery,
and REST communication with Trilio's Workload Manager API (wlm-api).
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import os
import re
import json

# Try importing openstacksdk for native OpenStack Ansible integration
try:
    import openstack
    HAS_OPENSTACKSDK = True
    OPENSTACKSDK_IMPORT_ERROR = None
except ImportError as e:
    HAS_OPENSTACKSDK = False
    OPENSTACKSDK_IMPORT_ERROR = str(e)

# Try importing requests for fallback direct Keystone auth and REST calls
try:
    import requests
    from requests.exceptions import RequestException
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


TRILIO_SERVICE_TYPES = ['workloads', 'workloadmgr', 'triliovault', 'backup']


def trilio_argument_spec(**kwargs):
    """
    Returns standard OpenStack connection arguments complemented with
    Trilio-specific options. Compatible with openstack.cloud argument specs.
    """
    spec = dict(
        # Standard OpenStack arguments
        cloud=dict(type='raw'),
        auth_type=dict(type='str'),
        auth=dict(type='dict', no_log=True),
        region_name=dict(type='str'),
        validate_certs=dict(type='bool', default=True, aliases=['verify']),
        ca_cert=dict(type='str', aliases=['cacert']),
        client_cert=dict(type='str', aliases=['cert']),
        client_key=dict(type='str', no_log=True, aliases=['key']),
        interface=dict(
            type='str',
            default='public',
            choices=['public', 'internal', 'admin'],
            aliases=['endpoint_type']
        ),
        api_timeout=dict(type='int'),
        timeout=dict(type='int', default=180),
        # Trilio-specific endpoint override
        trilio_endpoint=dict(type='str', default=None),
    )
    spec.update(kwargs)
    return spec


class TrilioClient:
    """
    Client for communicating with Trilio for OpenStack (wlm-api).
    Authenticates to Keystone (leveraging openstacksdk or direct Keystone v3 REST),
    resolves the Trilio endpoint from Keystone service catalog, and provides
    methods for Trilio API operations.
    """

    def __init__(self, module):
        self.module = module
        self.params = module.params
        self.token = None
        self.project_id = None
        self.endpoint = None
        self.conn = None
        self.session = None
        self.verify = self.params.get('validate_certs', True)
        if self.params.get('ca_cert'):
            self.verify = self.params.get('ca_cert')
        self.timeout = self.params.get('timeout', 180)

        # 1. Authenticate to Keystone and discover endpoint
        self._authenticate()

    def _authenticate(self):
        """
        Authenticate using openstacksdk if available, or fall back to
        direct Keystone v3 REST authentication.
        """
        if HAS_OPENSTACKSDK:
            self._auth_via_openstacksdk()
        elif HAS_REQUESTS:
            self._auth_via_keystone_rest()
        else:
            self.module.fail_json(
                msg="Either 'openstacksdk' or 'requests' Python package is required for authentication."
            )

    def _auth_via_openstacksdk(self):
        """
        Connect to OpenStack using openstacksdk (respecting clouds.yaml,
        environment variables, or auth dictionary).
        """
        cloud_config = self.params.get('cloud')
        conn_kwargs = {}

        if isinstance(cloud_config, dict):
            conn_kwargs = dict(cloud_config)
        else:
            if cloud_config:
                conn_kwargs['cloud'] = cloud_config
            if self.params.get('auth'):
                conn_kwargs['auth'] = self.params.get('auth')
            if self.params.get('auth_type'):
                conn_kwargs['auth_type'] = self.params.get('auth_type')
            if self.params.get('region_name'):
                conn_kwargs['region_name'] = self.params.get('region_name')
            if self.params.get('interface'):
                conn_kwargs['interface'] = self.params.get('interface')
            if self.params.get('validate_certs') is not None:
                conn_kwargs['verify'] = self.params.get('validate_certs')
            if self.params.get('ca_cert'):
                conn_kwargs['cacert'] = self.params.get('ca_cert')
            if self.params.get('client_cert'):
                conn_kwargs['cert'] = self.params.get('client_cert')
            if self.params.get('client_key'):
                conn_kwargs['key'] = self.params.get('client_key')
            if self.params.get('api_timeout'):
                conn_kwargs['api_timeout'] = self.params.get('api_timeout')

        try:
            self.conn = openstack.connect(**conn_kwargs)
        except Exception as e:
            # If a named cloud was passed (e.g. 'openstack') but not found in clouds.yaml,
            # and OS_* environment variables are present, automatically retry with environment variables
            err_msg = str(e).lower()
            if ('not found' in err_msg or 'no such cloud' in err_msg) and os.environ.get('OS_AUTH_URL'):
                try:
                    conn_kwargs.pop('cloud', None)
                    self.conn = openstack.connect(**conn_kwargs)
                except Exception as env_err:
                    if HAS_REQUESTS:
                        self._auth_via_keystone_rest()
                        return
                    self.module.fail_json(msg="Failed to connect to OpenStack using environment variables: %s" % str(env_err))
            elif HAS_REQUESTS and os.environ.get('OS_AUTH_URL'):
                self._auth_via_keystone_rest()
                return
            else:
                self.module.fail_json(msg="Failed to connect to OpenStack: %s" % str(e))

        try:
            # Extract Keystone token
            if hasattr(self.conn, 'session') and self.conn.session:
                self.token = self.conn.session.get_token()
                self.project_id = self.conn.session.get_project_id()
            elif hasattr(self.conn, 'auth_token'):
                self.token = self.conn.auth_token
                self.project_id = getattr(self.conn, 'current_project_id', None)
        except Exception as e:
            if HAS_REQUESTS and os.environ.get('OS_AUTH_URL'):
                self._auth_via_keystone_rest()
                return
            self.module.fail_json(msg="Failed to obtain Keystone authentication token: %s" % str(e))

        # Discover or set Trilio endpoint
        self._resolve_endpoint()

    def _auth_via_keystone_rest(self):
        """
        Fallback direct Keystone v3 REST authentication.
        Useful in environments where openstacksdk is not installed but
        standard OpenStack environment variables or auth dictionary are present.
        """
        auth_dict = self.params.get('auth') or {}
        auth_url = auth_dict.get('auth_url') or os.environ.get('OS_AUTH_URL')
        username = auth_dict.get('username') or os.environ.get('OS_USERNAME')
        password = auth_dict.get('password') or os.environ.get('OS_PASSWORD')
        project_name = auth_dict.get('project_name') or os.environ.get('OS_PROJECT_NAME') or os.environ.get('OS_TENANT_NAME')
        project_id = auth_dict.get('project_id') or os.environ.get('OS_PROJECT_ID') or os.environ.get('OS_TENANT_ID')
        user_domain = auth_dict.get('user_domain_name') or os.environ.get('OS_USER_DOMAIN_NAME') or os.environ.get('OS_USER_DOMAIN_ID', 'Default')
        project_domain = auth_dict.get('project_domain_name') or os.environ.get('OS_PROJECT_DOMAIN_NAME') or os.environ.get('OS_PROJECT_DOMAIN_ID', 'Default')
        app_cred_id = auth_dict.get('application_credential_id') or os.environ.get('OS_APPLICATION_CREDENTIAL_ID')
        app_cred_secret = auth_dict.get('application_credential_secret') or os.environ.get('OS_APPLICATION_CREDENTIAL_SECRET')

        if not auth_url:
            self.module.fail_json(
                msg="No OpenStack authentication details found. Provide 'cloud' or 'auth' in playbook, "
                    "or set standard OS_* environment variables."
            )

        auth_url = auth_url.rstrip('/')
        if not auth_url.endswith('/v3') and '/v3' not in auth_url:
            tokens_url = auth_url + '/v3/auth/tokens'
        elif auth_url.endswith('/v3'):
            tokens_url = auth_url + '/auth/tokens'
        else:
            tokens_url = auth_url + '/tokens'

        if app_cred_id and app_cred_secret:
            auth_body = {
                "auth": {
                    "identity": {
                        "methods": ["application_credential"],
                        "application_credential": {
                            "id": app_cred_id,
                            "secret": app_cred_secret
                        }
                    }
                }
            }
        elif username and password:
            scope = {}
            if project_id:
                scope = {"project": {"id": project_id}}
            elif project_name:
                scope = {
                    "project": {
                        "name": project_name,
                        "domain": {"name": project_domain}
                    }
                }
            auth_body = {
                "auth": {
                    "identity": {
                        "methods": ["password"],
                        "password": {
                            "user": {
                                "name": username,
                                "domain": {"name": user_domain},
                                "password": password
                            }
                        }
                    },
                    "scope": scope
                }
            }
        else:
            self.module.fail_json(
                msg="Insufficient Keystone credentials provided (username/password or application credentials required)."
            )

        try:
            resp = requests.post(
                tokens_url,
                json=auth_body,
                headers={"Content-Type": "application/json"},
                verify=self.verify,
                timeout=self.timeout
            )
        except RequestException as e:
            self.module.fail_json(msg="Keystone authentication request failed: %s" % str(e))

        if resp.status_code not in (200, 201):
            self.module.fail_json(
                msg="Keystone authentication rejected (HTTP %s): %s" % (resp.status_code, resp.text)
            )

        self.token = resp.headers.get('X-Subject-Token')
        try:
            data = resp.json()
            token_info = data.get('token', {})
            project_info = token_info.get('project', {})
            self.project_id = project_info.get('id') or project_id
            self._catalog = token_info.get('catalog', [])
        except Exception as e:
            self.module.fail_json(msg="Failed to parse Keystone token response: %s" % str(e))

        self._resolve_endpoint()

    def _resolve_endpoint(self):
        """
        Discovers the Trilio Workload Manager endpoint from the Keystone
        service catalog or uses the user-provided `trilio_endpoint` override.
        """
        # 1. Check explicit override
        if self.params.get('trilio_endpoint'):
            self.endpoint = self.params['trilio_endpoint'].rstrip('/')
            return

        interface = self.params.get('interface', 'public')
        region_name = self.params.get('region_name')

        # 2. Try openstacksdk endpoint discovery
        if self.conn:
            for s_type in TRILIO_SERVICE_TYPES:
                try:
                    ep = None
                    if hasattr(self.conn, 'get_endpoint'):
                        ep = self.conn.get_endpoint(
                            service_type=s_type,
                            interface=interface,
                            region_name=region_name
                        )
                    elif hasattr(self.conn, 'endpoint_for'):
                        ep = self.conn.endpoint_for(
                            service_type=s_type,
                            interface=interface,
                            region_name=region_name
                        )
                    if not ep and hasattr(self.conn, 'session') and hasattr(self.conn.session, 'get_endpoint'):
                        ep = self.conn.session.get_endpoint(
                            service_type=s_type,
                            interface=interface,
                            region_name=region_name
                        )
                    if ep:
                        self.endpoint = self._format_endpoint(ep)
                        return
                except Exception:
                    continue

        # 3. Try catalog inspection from Keystone REST token response
        catalog = getattr(self, '_catalog', None)
        if catalog:
            for entry in catalog:
                s_type = entry.get('type')
                s_name = entry.get('name')
                if s_type in TRILIO_SERVICE_TYPES or s_name in TRILIO_SERVICE_TYPES:
                    for ep in entry.get('endpoints', []):
                        if ep.get('interface') == interface:
                            if not region_name or ep.get('region') == region_name:
                                self.endpoint = self._format_endpoint(ep.get('url'))
                                return

        self.module.fail_json(
            msg="Trilio Workload Manager service (workloads/workloadmgr) not found in Keystone catalog. "
                "Specify 'trilio_endpoint' parameter in your task or register Trilio in the service catalog."
        )

    def _format_endpoint(self, url):
        """
        Format endpoint URL, substituting %(project_id)s or %(tenant_id)s if present,
        and stripping trailing slashes.
        """
        if not url:
            return None
        url = url.rstrip('/')
        if self.project_id:
            url = url.replace('%(project_id)s', self.project_id)
            url = url.replace('%(tenant_id)s', self.project_id)
        return url

    def request(self, method, path, params=None, json_data=None):
        """
        Executes an authenticated HTTP request to Trilio wlm-api.
        """
        if not self.endpoint:
            self.module.fail_json(msg="Trilio endpoint is not configured.")

        # Ensure path begins with /
        if not path.startswith('/'):
            path = '/' + path

        # Construct full URL.
        # If endpoint already has /v1 or /v1/{project_id}, avoid duplicating
        if path.startswith('/v1') and '/v1' in self.endpoint:
            # Strip /v1 from path if endpoint already contains /v1
            path = path[3:]

        full_url = self.endpoint + path

        headers = {
            'X-Auth-Token': self.token,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        if self.project_id:
            headers['X-Auth-Project-Id'] = self.project_id

        # Use openstacksdk session if available, else requests
        try:
            if self.conn and hasattr(self.conn, 'session') and self.conn.session:
                resp = self.conn.session.request(
                    method=method,
                    url=full_url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=self.timeout
                )
            elif HAS_REQUESTS:
                resp = requests.request(
                    method=method,
                    url=full_url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    verify=self.verify,
                    timeout=self.timeout
                )
            else:
                self.module.fail_json(msg="No HTTP client library available to execute request.")
        except Exception as e:
            self.module.fail_json(
                msg="Failed to connect to Trilio API at %s: %s" % (full_url, str(e))
            )

        # Handle HTTP status codes
        if resp.status_code == 401:
            self.module.fail_json(
                msg="Unauthorized (HTTP 401): Keystone token rejected by Trilio Workload Manager."
            )
        elif resp.status_code == 403:
            self.module.fail_json(
                msg="Forbidden (HTTP 403): User lacks permissions for Trilio Workload Manager API."
            )
        elif resp.status_code == 404:
            return None
        elif resp.status_code >= 400:
            self.module.fail_json(
                msg="Trilio API request error (HTTP %s): %s" % (resp.status_code, resp.text)
            )

        if resp.status_code == 204:
            return {}

        try:
            return resp.json()
        except Exception:
            return resp.text

    def get(self, path, params=None):
        return self.request('GET', path, params=params)

    def post(self, path, json_data=None):
        return self.request('POST', path, json_data=json_data)

    def put(self, path, json_data=None):
        return self.request('PUT', path, json_data=json_data)

    def delete(self, path):
        return self.request('DELETE', path)

    def list_workloads(self, project_id=None, all_projects=False, detailed=True, nfs_share=None):
        """
        List workloads for a given project or all projects.
        Target path: /v1/{project_id}/workloads/detail or /v1/{project_id}/workloads
        """
        target_project = project_id or self.project_id
        if not target_project:
            self.module.fail_json(
                msg="No OpenStack project ID available. Provide project_id parameter or scope authentication to a project."
            )

        # Build path ensuring /v1/{target_project} prefix if needed
        endpoint_has_project = bool(re.search(r'/[0-9a-fA-F]{32}', self.endpoint) or re.search(r'/[0-9a-fA-F-]{36}', self.endpoint))
        if endpoint_has_project:
            subpath = '/workloads/detail' if detailed else '/workloads'
        else:
            subpath = '/v1/%s/workloads/detail' % target_project if detailed else '/v1/%s/workloads' % target_project

        params = {}
        if all_projects:
            params['all_workloads'] = 'True'
        if nfs_share:
            params['nfs_share'] = nfs_share

        result = self.get(subpath, params=params)
        if isinstance(result, dict) and 'workloads' in result:
            return result['workloads']
        elif isinstance(result, list):
            return result
        return []

    def get_workload(self, workload_id, project_id=None):
        """
        Retrieve a single workload by UUID.
        """
        target_project = project_id or self.project_id
        if not target_project:
            self.module.fail_json(msg="No OpenStack project ID available.")

        endpoint_has_project = bool(re.search(r'/[0-9a-fA-F]{32}', self.endpoint) or re.search(r'/[0-9a-fA-F-]{36}', self.endpoint))
        if endpoint_has_project:
            subpath = '/workloads/%s' % workload_id
        else:
            subpath = '/v1/%s/workloads/%s' % (target_project, workload_id)

        result = self.get(subpath)
        if isinstance(result, dict) and 'workload' in result:
            return result['workload']
        return result
