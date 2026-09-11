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


TRILIO_SERVICE_TYPES = ['workloads', 'workloadmgr', 'triliovault', 'triliovaultwlm', 'wlm', 'backup']


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
        validate_certs=dict(type='bool', aliases=['verify']),
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
        validate_certs = self.params.get('validate_certs')
        if validate_certs is not None:
            self.verify = validate_certs
        elif os.environ.get('OS_INSECURE', '').lower() in ('true', '1', 'yes'):
            self.verify = False
        elif os.environ.get('OS_VERIFY', '').lower() in ('false', '0', 'no'):
            self.verify = False
        else:
            self.verify = True

        if self.params.get('ca_cert'):
            self.verify = self.params.get('ca_cert')
        elif os.environ.get('OS_CACERT'):
            self.verify = os.environ.get('OS_CACERT')
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
            elif not self.verify:
                conn_kwargs['verify'] = False
            if self.params.get('ca_cert'):
                conn_kwargs['cacert'] = self.params.get('ca_cert')
            elif os.environ.get('OS_CACERT'):
                conn_kwargs['cacert'] = os.environ.get('OS_CACERT')
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

            if not self.project_id and hasattr(self.conn, 'current_project_id'):
                self.project_id = self.conn.current_project_id
        except Exception as e:
            if HAS_REQUESTS and os.environ.get('OS_AUTH_URL'):
                self._auth_via_keystone_rest()
                return
            self.module.fail_json(msg="Failed to obtain Keystone authentication token: %s" % str(e))

        # Extract Keystone service catalog from openstacksdk connection
        try:
            if hasattr(self.conn, 'session') and self.conn.session and self.conn.session.auth:
                access = self.conn.session.auth.get_access(self.conn.session)
                if hasattr(access, 'service_catalog'):
                    sc = access.service_catalog
                    if hasattr(sc, 'get_data'):
                        self._catalog = sc.get_data()
                    elif hasattr(sc, 'catalog'):
                        self._catalog = sc.catalog
        except Exception:
            pass

        if not getattr(self, '_catalog', None) and hasattr(self.conn, 'service_catalog'):
            try:
                sc = self.conn.service_catalog
                if hasattr(sc, 'get_data'):
                    self._catalog = sc.get_data()
                elif hasattr(sc, 'catalog'):
                    self._catalog = sc.catalog
                elif isinstance(sc, list):
                    self._catalog = sc
            except Exception:
                pass

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
            self._post_process_endpoint()
            return

        interface = self.params.get('interface', 'public')
        region_name = self.params.get('region_name') or os.environ.get('OS_REGION_NAME')

        # Extract service catalog if not already cached
        catalog = getattr(self, '_catalog', None)
        if not catalog and self.conn:
            try:
                if hasattr(self.conn, 'session') and self.conn.session and self.conn.session.auth:
                    access = self.conn.session.auth.get_access(self.conn.session)
                    if hasattr(access, 'service_catalog'):
                        sc = access.service_catalog
                        if hasattr(sc, 'get_data'):
                            catalog = sc.get_data()
                        elif hasattr(sc, 'catalog'):
                            catalog = sc.catalog
            except Exception:
                pass
            if not catalog and hasattr(self.conn, 'service_catalog'):
                sc = self.conn.service_catalog
                if hasattr(sc, 'get_data'):
                    catalog = sc.get_data()
                elif hasattr(sc, 'catalog'):
                    catalog = sc.catalog
                elif isinstance(sc, list):
                    catalog = sc

        # 2. Inspect raw service catalog (handles custom names like TrilioVaultWLM and standard type workloads)
        if catalog:
            for entry in catalog:
                s_type = str(entry.get('type') or '').strip().lower()
                s_name = str(entry.get('name') or '').strip().lower()
                if s_type in TRILIO_SERVICE_TYPES or s_name in TRILIO_SERVICE_TYPES:
                    endpoints = entry.get('endpoints', [])
                    # Match exact interface and region
                    for ep in endpoints:
                        ep_interface = ep.get('interface')
                        ep_region = ep.get('region') or ep.get('region_id')
                        url = ep.get('url') or (ep.get('publicURL') if interface == 'public' else (ep.get('internalURL') if interface == 'internal' else ep.get('adminURL')))
                        if url:
                            if not ep_interface or ep_interface == interface:
                                if not region_name or ep_region == region_name:
                                    self.endpoint = self._format_endpoint(url)
                                    self._post_process_endpoint()
                                    return
                    # Fallback to matching interface across any region
                    for ep in endpoints:
                        ep_interface = ep.get('interface')
                        url = ep.get('url') or (ep.get('publicURL') if interface == 'public' else (ep.get('internalURL') if interface == 'internal' else ep.get('adminURL')))
                        if url and (not ep_interface or ep_interface == interface):
                            self.endpoint = self._format_endpoint(url)
                            self._post_process_endpoint()
                            return
                    # Fallback to any URL for this service
                    for ep in endpoints:
                        url = ep.get('url') or ep.get('publicURL') or ep.get('internalURL') or ep.get('adminURL')
                        if url:
                            self.endpoint = self._format_endpoint(url)
                            self._post_process_endpoint()
                            return

        # 3. Try keystoneauth session get_endpoint
        if self.conn and hasattr(self.conn, 'session') and self.conn.session:
            for s_identifier in TRILIO_SERVICE_TYPES:
                for arg_key in ['service_type', 'service_name']:
                    try:
                        kwargs = {arg_key: s_identifier, 'interface': interface}
                        if region_name:
                            kwargs['region_name'] = region_name
                        ep = self.conn.session.get_endpoint(**kwargs)
                        if ep:
                            self.endpoint = self._format_endpoint(ep)
                            self._post_process_endpoint()
                            return
                    except Exception:
                        pass

        # 4. Try openstacksdk connection endpoint discovery
        if self.conn:
            for s_identifier in TRILIO_SERVICE_TYPES:
                try:
                    kwargs = {'service_type': s_identifier, 'interface': interface}
                    if region_name:
                        kwargs['region_name'] = region_name
                    ep = None
                    if hasattr(self.conn, 'get_endpoint'):
                        ep = self.conn.get_endpoint(**kwargs)
                    elif hasattr(self.conn, 'endpoint_for'):
                        ep = self.conn.endpoint_for(**kwargs)
                    if ep:
                        self.endpoint = self._format_endpoint(ep)
                        self._post_process_endpoint()
                        return
                except Exception:
                    continue

        found_services = []
        if catalog:
            for entry in catalog:
                found_services.append("%s (%s)" % (entry.get('name'), entry.get('type')))
        msg = "Trilio Workload Manager service (workloads/workloadmgr/TrilioVaultWLM) not found in Keystone catalog."
        if found_services:
            msg += " Available services in catalog: [%s]." % ", ".join(found_services)
        msg += " Specify 'trilio_endpoint' parameter in your task or register Trilio in the service catalog."
        self.module.fail_json(msg=msg)

    def _post_process_endpoint(self):
        """
        Extracts project_id from endpoint URL if not already determined.
        """
        if not self.project_id and self.endpoint:
            m = re.search(r'/v1/([0-9a-fA-F]{32}|[0-9a-fA-F-]{36})', self.endpoint)
            if m:
                self.project_id = m.group(1)

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

    @property
    def base_endpoint(self):
        """
        Returns the root/base URL of the Trilio service without /v1 or project_id suffix.
        E.g. http://tvm.domain:8780/v1/UUID -> http://tvm.domain:8780
        """
        if not self.endpoint:
            return None
        base = re.sub(r'/v1(/[0-9a-fA-F-]{32,36})?/?$', '', self.endpoint)
        return base.rstrip('/')

    def _execute_http(self, method, full_url, params=None, json_data=None, allow_404=True):
        """
        Low-level HTTP execution with token authentication and error mapping.
        """
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
            if allow_404:
                return None
            self.module.fail_json(
                msg="Resource not found (HTTP 404) at %s: %s" % (full_url, resp.text)
            )
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

    def request(self, method, path, params=None, json_data=None, allow_404=True):
        """
        Executes an authenticated HTTP request to Trilio wlm-api.
        Path is relative to self.endpoint (project-scoped or service endpoint).
        """
        if not self.endpoint:
            self.module.fail_json(msg="Trilio endpoint is not configured.")

        # Ensure path begins with /
        if not path.startswith('/'):
            path = '/' + path

        # Construct full URL.
        # If endpoint already has /v1 or /v1/{project_id}, avoid duplicating
        if path.startswith('/v1') and '/v1' in self.endpoint:
            path = path[3:]

        full_url = self.endpoint + path
        return self._execute_http(method, full_url, params=params, json_data=json_data, allow_404=allow_404)

    def dms_request(self, method, path, params=None, json_data=None, allow_404=True):
        """
        Executes an authenticated HTTP request against Dynamic Mounting Service (DMS) endpoints
        such as /backup_targets and /backup_target_types.
        Resolves to base_endpoint or endpoint with fallback handling.
        """
        if not self.endpoint:
            self.module.fail_json(msg="Trilio endpoint is not configured.")

        if not path.startswith('/'):
            path = '/' + path

        base = self.base_endpoint or self.endpoint
        full_url = base + path

        res = self._execute_http(method, full_url, params=params, json_data=json_data, allow_404=True)
        if res is None:
            # If 404, check with /v1 prefix if not already present
            if not path.startswith('/v1'):
                v1_url = base + '/v1' + path
                res_v1 = self._execute_http(method, v1_url, params=params, json_data=json_data, allow_404=True)
                if res_v1 is not None:
                    return res_v1

            if not allow_404:
                self.module.fail_json(msg="DMS resource not found (HTTP 404) at %s" % full_url)
            return None

        return res

    def get(self, path, params=None):
        return self.request('GET', path, params=params)

    def post(self, path, json_data=None, params=None):
        return self.request('POST', path, json_data=json_data, params=params)

    def put(self, path, json_data=None, params=None):
        return self.request('PUT', path, json_data=json_data, params=params)

    def delete(self, path, params=None):
        return self.request('DELETE', path, params=params)

    # -------------------------------------------------------------------------
    # DMS (Dynamic Mounting Service) & Version Validation
    # -------------------------------------------------------------------------

    def validate_dms_support(self, min_version="6.2"):
        """
        Validates that the connected Trilio instance supports the Dynamic Mounting Service (DMS)
        API and is version 6.2 or newer.
        If DMS endpoints are not found or return 404, fails with an informative error.
        """
        res = self.dms_request('GET', '/backup_targets')
        if res is None:
            self.module.fail_json(
                msg=(
                    "Trilio %s or newer is required to manage backup targets and backup target types "
                    "using the Dynamic Mounting Service (DMS) API. The '/backup_targets' endpoint was "
                    "not found on Trilio endpoint '%s'. Earlier Trilio versions (4.x/5.x/6.0/6.1) used "
                    "static container mounts and do not support dynamic API-driven target creation."
                    % (min_version, self.endpoint or self.base_endpoint)
                )
            )
        return True

    # -------------------------------------------------------------------------
    # Backup Target Operations (Trilio 6.2+ DMS)
    # -------------------------------------------------------------------------

    def list_backup_targets(self):
        """
        List all backup targets configured in Trilio via DMS.
        GET /backup_targets
        """
        res = self.dms_request('GET', '/backup_targets')
        if isinstance(res, dict) and 'backup_targets' in res:
            return res['backup_targets']
        elif isinstance(res, list):
            return res
        return []

    def get_backup_target(self, backup_target_id):
        """
        Retrieve a single backup target by UUID.
        GET /backup_targets/{id}
        """
        res = self.dms_request('GET', '/backup_targets/%s' % backup_target_id)
        if isinstance(res, dict) and 'backup_target' in res:
            return res['backup_target']
        return res

    def find_backup_target(self, name=None, btt_name=None, filesystem_export=None,
                           s3_endpoint_url=None, s3_bucket=None, target_id=None):
        """
        Find an existing backup target matching search criteria.
        """
        targets = self.list_backup_targets()
        for bt in targets:
            if target_id and bt.get('id') == target_id:
                return bt
            if filesystem_export and bt.get('filesystem_export') == filesystem_export:
                return bt
            if s3_endpoint_url and s3_bucket:
                if bt.get('s3_endpoint_url') == s3_endpoint_url and bt.get('s3_bucket') == s3_bucket:
                    return bt
            if name and (bt.get('name') == name or bt.get('btt_name') == name):
                return bt
            if btt_name and bt.get('btt_name') == btt_name:
                return bt
        return None

    def create_backup_target(self, target_type, filesystem_export=None, nfs_mount_opts=None,
                             s3_endpoint_url=None, s3_bucket=None, secret_ref=None,
                             btt_name=None, is_default=0, immutable=0, metadata=None):
        """
        Create a backup target using Trilio 6.2+ DMS API.
        POST /backup_targets
        """
        target_data = {
            'type': target_type,
            'is_default': 1 if is_default else 0,
        }
        if btt_name:
            target_data['btt_name'] = btt_name

        if target_type == 'nfs':
            if not filesystem_export:
                self.module.fail_json(msg="'filesystem_export' is required when backup target type is 'nfs'.")
            target_data['filesystem_export'] = filesystem_export
            if nfs_mount_opts:
                target_data['nfs_mount_opts'] = nfs_mount_opts

        elif target_type == 's3':
            if not s3_endpoint_url or not s3_bucket:
                self.module.fail_json(msg="'s3_endpoint_url' and 's3_bucket' are required when backup target type is 's3'.")
            if not secret_ref:
                self.module.fail_json(
                    msg="'secret_ref' (Barbican secret URL) is required for S3 backup targets in Trilio 6.2+ DMS."
                )
            target_data['s3_endpoint_url'] = s3_endpoint_url
            target_data['s3_bucket'] = s3_bucket
            target_data['secret_ref'] = secret_ref
            if immutable:
                target_data['immutable'] = 1 if immutable else 0

        if metadata:
            target_data['metadata'] = metadata

        payload = {'backup_target': target_data}
        res = self.dms_request('POST', '/backup_targets', json_data=payload)
        if isinstance(res, dict) and 'backup_target' in res:
            return res['backup_target']
        return res

    def update_backup_target(self, backup_target_id, nfs_mount_opts=None, secret_ref=None,
                             metadata=None, is_default=None):
        """
        Update mutable attributes of an existing backup target (PUT /backup_targets/{id}).
        """
        target_data = {}
        if nfs_mount_opts is not None:
            target_data['nfs_mount_opts'] = nfs_mount_opts
        if secret_ref is not None:
            target_data['secret_ref'] = secret_ref
        if metadata is not None:
            target_data['metadata'] = metadata
        if is_default is not None:
            target_data['is_default'] = 1 if is_default else 0

        payload = {'backup_target': target_data}
        res = self.dms_request('PUT', '/backup_targets/%s' % backup_target_id, json_data=payload)
        if isinstance(res, dict) and 'backup_target' in res:
            return res['backup_target']
        return res

    def delete_backup_target(self, backup_target_id):
        """
        Delete an existing backup target (DELETE /backup_targets/{id}).
        """
        return self.dms_request('DELETE', '/backup_targets/%s' % backup_target_id)

    def set_default_backup_target(self, backup_target_id):
        """
        Set a backup target as the default target.
        """
        return self.dms_request('GET', '/backup_targets/%s/set_default' % backup_target_id)

    # -------------------------------------------------------------------------
    # Backup Target Type (BTT) Operations
    # -------------------------------------------------------------------------

    def list_backup_target_types(self):
        """
        List all backup target types (GET /backup_target_types).
        """
        res = self.dms_request('GET', '/backup_target_types')
        if isinstance(res, dict) and 'backup_target_types' in res:
            return res['backup_target_types']
        elif isinstance(res, list):
            return res
        return []

    def get_backup_target_type(self, btt_id):
        """
        Get backup target type details by UUID (GET /backup_target_types/{id}).
        """
        res = self.dms_request('GET', '/backup_target_types/%s' % btt_id)
        if isinstance(res, dict) and 'backup_target_types' in res:
            return res['backup_target_types']
        elif isinstance(res, dict) and 'backup_target_type' in res:
            return res['backup_target_type']
        return res

    def find_backup_target_type(self, name=None, btt_id=None):
        """
        Find a backup target type matching name or UUID.
        """
        btts = self.list_backup_target_types()
        for btt in btts:
            if btt_id and btt.get('id') == btt_id:
                return btt
            if name and btt.get('name') == name:
                return btt
        return None

    def create_backup_target_type(self, name, backup_target_id, description=None,
                                  is_public=True, metadata=None):
        """
        Create a backup target type (POST /backup_target_types).
        """
        btt_data = {
            'name': name,
            'backup_targets_id': backup_target_id,
            'is_public': is_public
        }
        if description:
            btt_data['description'] = description
        if metadata:
            btt_data['backup_target_type_metadata'] = metadata

        payload = {'backup_target_type': btt_data}
        res = self.dms_request('POST', '/backup_target_types', json_data=payload)
        if isinstance(res, dict) and 'backup_target_type' in res:
            return res['backup_target_type']
        return res

    def delete_backup_target_type(self, btt_id):
        """
        Delete a backup target type (DELETE /backup_target_types/{id}).
        """
        return self.dms_request('DELETE', '/backup_target_types/%s' % btt_id)

    def add_projects_to_btt(self, btt_id, project_ids):
        """
        Assign projects to a backup target type (POST /backup_target_types/{id}/add_projects).
        """
        if isinstance(project_ids, str):
            project_ids = [project_ids]
        payload = {'add_projects': project_ids}
        return self.dms_request('POST', '/backup_target_types/%s/add_projects' % btt_id, json_data=payload)

    def remove_projects_from_btt(self, btt_id, project_ids):
        """
        Remove projects from a backup target type (POST /backup_target_types/{id}/remove_projects).
        """
        if isinstance(project_ids, str):
            project_ids = [project_ids]
        payload = {'remove_projects': project_ids}
        return self.dms_request('POST', '/backup_target_types/%s/remove_projects' % btt_id, json_data=payload)

    # -------------------------------------------------------------------------
    # Workload Operations
    # -------------------------------------------------------------------------

    def list_workload_types(self, project_id=None):
        """
        List supported workload types (Parallel / Serial).
        GET /v1/{project_id}/workload_types/detail
        """
        target_project = project_id or self.project_id
        if not target_project:
            self.module.fail_json(msg="No OpenStack project ID available.")

        endpoint_has_project = bool(self.endpoint and (re.search(r'/[0-9a-fA-F]{32}', self.endpoint) or re.search(r'/[0-9a-fA-F-]{36}', self.endpoint)))
        if endpoint_has_project:
            subpath = '/workload_types/detail'
        else:
            subpath = '/v1/%s/workload_types/detail' % target_project

        res = self.get(subpath)
        if isinstance(res, dict) and 'workload_types' in res:
            return res['workload_types']
        elif isinstance(res, list):
            return res
        return []

    def list_workloads(self, project_id=None, all_projects=False, detailed=True,
                       nfs_share=None, s3_bucket=None, backup_target=None,
                       backup_target_type=None):
        """
        List workloads for a given project or all projects.
        Supports filtering by storage destination:
          - nfs_share: Upstream API-supported query parameter and client-side match
          - s3_bucket: Filter workloads targeting a specific S3 bucket
          - backup_target: Unified filter matching NFS share, S3 bucket, endpoint, or target name
          - backup_target_type: Filter by Backup Target Type (BTT) name or UUID
        Target path: /v1/{project_id}/workloads/detail or /v1/{project_id}/workloads
        """
        target_project = project_id or self.project_id
        if not target_project:
            self.module.fail_json(
                msg="No OpenStack project ID available. Provide project_id parameter or scope authentication to a project."
            )

        endpoint_has_project = bool(self.endpoint and (re.search(r'/[0-9a-fA-F]{32}', self.endpoint) or re.search(r'/[0-9a-fA-F-]{36}', self.endpoint)))
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
        workloads = []
        if isinstance(result, dict) and 'workloads' in result:
            workloads = result['workloads']
        elif isinstance(result, list):
            workloads = result

        # Apply storage destination filtering (S3 bucket, NFS share, Backup Target, BTT)
        if s3_bucket or backup_target or backup_target_type or nfs_share:
            filtered = []
            for wl in workloads:
                storage_url = str(wl.get('storage_url') or '')
                media_target = str(wl.get('backup_media_target') or '')
                wl_btt = str(wl.get('backup_target_types') or wl.get('backup_target_type') or '')
                metadata = wl.get('metadata') or {}
                meta_btt = str(metadata.get('backup_target_types') or metadata.get('btt') or '')
                meta_bucket = str(metadata.get('s3_bucket') or metadata.get('bucket') or '')

                # Filter by s3_bucket
                if s3_bucket:
                    bucket_matched = (
                        s3_bucket in storage_url or
                        s3_bucket == media_target or
                        s3_bucket in media_target or
                        s3_bucket == meta_bucket or
                        s3_bucket in meta_bucket
                    )
                    if not bucket_matched:
                        continue

                # Filter by nfs_share
                if nfs_share:
                    nfs_matched = (
                        nfs_share == storage_url or
                        nfs_share in storage_url or
                        nfs_share == media_target or
                        nfs_share in media_target
                    )
                    if not nfs_matched:
                        continue

                # Filter by backup_target_type (BTT name or UUID)
                if backup_target_type:
                    btt_matched = (
                        backup_target_type == wl_btt or
                        backup_target_type == meta_btt or
                        backup_target_type in wl_btt or
                        backup_target_type in meta_btt
                    )
                    if not btt_matched:
                        continue

                # Filter by generic backup_target
                if backup_target:
                    target_matched = (
                        backup_target == storage_url or
                        backup_target in storage_url or
                        backup_target == media_target or
                        backup_target in media_target or
                        backup_target == wl_btt or
                        backup_target == meta_btt or
                        backup_target == meta_bucket or
                        backup_target in meta_bucket
                    )
                    if not target_matched:
                        continue

                filtered.append(wl)
            workloads = filtered

        return workloads

    def get_workload(self, workload_id, project_id=None):
        """
        Retrieve a single workload by UUID.
        """
        target_project = project_id or self.project_id
        if not target_project:
            self.module.fail_json(msg="No OpenStack project ID available.")

        endpoint_has_project = bool(self.endpoint and (re.search(r'/[0-9a-fA-F]{32}', self.endpoint) or re.search(r'/[0-9a-fA-F-]{36}', self.endpoint)))
        if endpoint_has_project:
            subpath = '/workloads/%s' % workload_id
        else:
            subpath = '/v1/%s/workloads/%s' % (target_project, workload_id)

        result = self.get(subpath)
        if isinstance(result, dict) and 'workload' in result:
            return result['workload']
        return result

    def get_workload_by_name(self, name, project_id=None):
        """
        Find a single workload matching the given name within the project.
        """
        workloads = self.list_workloads(project_id=project_id, detailed=True)
        for wl in workloads:
            if wl.get('name') == name:
                return wl
        return None

    def create_workload(self, name, instances, workload_type_id=None, description=None,
                        backup_target_types=None, jobschedule=None, metadata=None,
                        source_platform='openstack', project_id=None):
        """
        Create a new workload (POST /v1/{project_id}/workloads).
        """
        target_project = project_id or self.project_id
        if not target_project:
            self.module.fail_json(msg="No OpenStack project ID available.")

        # Resolve workload_type_id if not provided
        if not workload_type_id:
            wl_types = self.list_workload_types(project_id=target_project)
            parallel_type = next((t for t in wl_types if 'parallel' in t.get('name', '').lower()), None)
            if parallel_type:
                workload_type_id = parallel_type.get('id')
            elif wl_types:
                workload_type_id = wl_types[0].get('id')
            else:
                workload_type_id = '272f3105-fhang-4b36-81cf-fb15b8054c25'

        # Format instances list: [{"instance-id": "UUID"}, ...]
        formatted_instances = []
        for inst in (instances or []):
            if isinstance(inst, dict):
                inst_id = inst.get('instance-id') or inst.get('id')
                if inst_id:
                    formatted_instances.append({'instance-id': str(inst_id)})
            elif isinstance(inst, str):
                formatted_instances.append({'instance-id': inst})

        wl_data = {
            'name': name,
            'workload_type_id': workload_type_id,
            'source_platform': source_platform or 'openstack',
            'instances': formatted_instances,
        }
        if description:
            wl_data['description'] = description
        if backup_target_types:
            wl_data['backup_target_types'] = backup_target_types
        if jobschedule:
            wl_data['jobschedule'] = jobschedule
        if metadata:
            wl_data['metadata'] = metadata

        endpoint_has_project = bool(self.endpoint and (re.search(r'/[0-9a-fA-F]{32}', self.endpoint) or re.search(r'/[0-9a-fA-F-]{36}', self.endpoint)))
        if endpoint_has_project:
            subpath = '/workloads'
        else:
            subpath = '/v1/%s/workloads' % target_project

        payload = {'workload': wl_data}
        res = self.post(subpath, json_data=payload)
        if isinstance(res, dict) and 'workload' in res:
            return res['workload']
        return res

    def update_workload(self, workload_id, name=None, description=None, instances=None,
                        jobschedule=None, metadata=None, project_id=None):
        """
        Update an existing workload (PUT /v1/{project_id}/workloads/{workload_id}).
        """
        target_project = project_id or self.project_id
        if not target_project:
            self.module.fail_json(msg="No OpenStack project ID available.")

        wl_data = {}
        if name is not None:
            wl_data['name'] = name
        if description is not None:
            wl_data['description'] = description
        if instances is not None:
            formatted_instances = []
            for inst in instances:
                if isinstance(inst, dict):
                    inst_id = inst.get('instance-id') or inst.get('id')
                    if inst_id:
                        formatted_instances.append({'instance-id': str(inst_id)})
                elif isinstance(inst, str):
                    formatted_instances.append({'instance-id': inst})
            wl_data['instances'] = formatted_instances
        if jobschedule is not None:
            wl_data['jobschedule'] = jobschedule
        if metadata is not None:
            wl_data['metadata'] = metadata

        endpoint_has_project = bool(self.endpoint and (re.search(r'/[0-9a-fA-F]{32}', self.endpoint) or re.search(r'/[0-9a-fA-F-]{36}', self.endpoint)))
        if endpoint_has_project:
            subpath = '/workloads/%s' % workload_id
        else:
            subpath = '/v1/%s/workloads/%s' % (target_project, workload_id)

        payload = {'workload': wl_data}
        res = self.put(subpath, json_data=payload)
        if isinstance(res, dict) and 'workload' in res:
            return res['workload']
        return res

    def delete_workload(self, workload_id, database_only=False, project_id=None):
        """
        Delete a workload (DELETE /v1/{project_id}/workloads/{workload_id}).
        """
        target_project = project_id or self.project_id
        if not target_project:
            self.module.fail_json(msg="No OpenStack project ID available.")

        endpoint_has_project = bool(self.endpoint and (re.search(r'/[0-9a-fA-F]{32}', self.endpoint) or re.search(r'/[0-9a-fA-F-]{36}', self.endpoint)))
        if endpoint_has_project:
            subpath = '/workloads/%s' % workload_id
        else:
            subpath = '/v1/%s/workloads/%s' % (target_project, workload_id)

        if database_only:
            subpath += '?database_only=True'

        return self.delete(subpath)

    def create_snapshot(self, workload_id, name=None, description=None, full=False, project_id=None):
        """
        Create a snapshot (backup) of a workload (POST /v1/{project_id}/workloads/{workload_id}).
        Query param 'full=True' is sent for full backups, omitted or 'full=False' for incremental.
        """
        target_project = project_id or self.project_id
        if not target_project:
            self.module.fail_json(msg="No OpenStack project ID available.")

        endpoint_has_project = bool(self.endpoint and (re.search(r'/[0-9a-fA-F]{32}', self.endpoint) or re.search(r'/[0-9a-fA-F-]{36}', self.endpoint)))
        if endpoint_has_project:
            subpath = '/workloads/%s' % workload_id
        else:
            subpath = '/v1/%s/workloads/%s' % (target_project, workload_id)

        params = {}
        if full:
            params['full'] = 'True'

        snap_data = {}
        if name:
            snap_data['name'] = name
        if description:
            snap_data['description'] = description
        if not snap_data:
            snap_data['name'] = 'Snapshot for %s' % workload_id

        payload = {'snapshot': snap_data}
        res = self.post(subpath, json_data=payload, params=params)
        if isinstance(res, dict) and 'snapshot' in res:
            return res['snapshot']
        return res

    def get_snapshot(self, snapshot_id, project_id=None):
        """
        Retrieve a single snapshot by UUID (GET /v1/{project_id}/snapshots/{snapshot_id}).
        """
        target_project = project_id or self.project_id
        if not target_project:
            self.module.fail_json(msg="No OpenStack project ID available.")

        endpoint_has_project = bool(self.endpoint and (re.search(r'/[0-9a-fA-F]{32}', self.endpoint) or re.search(r'/[0-9a-fA-F-]{36}', self.endpoint)))
        if endpoint_has_project:
            subpath = '/snapshots/%s' % snapshot_id
        else:
            subpath = '/v1/%s/snapshots/%s' % (target_project, snapshot_id)

        res = self.get(subpath)
        if isinstance(res, dict) and 'snapshot' in res:
            return res['snapshot']
        return res

    def list_snapshots(self, workload_id=None, project_id=None, all_snapshots=False):
        """
        List snapshots (GET /v1/{project_id}/snapshots).
        """
        target_project = project_id or self.project_id
        if not target_project:
            self.module.fail_json(msg="No OpenStack project ID available.")

        endpoint_has_project = bool(self.endpoint and (re.search(r'/[0-9a-fA-F]{32}', self.endpoint) or re.search(r'/[0-9a-fA-F-]{36}', self.endpoint)))
        if endpoint_has_project:
            subpath = '/snapshots'
        else:
            subpath = '/v1/%s/snapshots' % target_project

        params = {}
        if workload_id:
            params['workload_id'] = workload_id
        if all_snapshots:
            params['all'] = 'True'

        res = self.get(subpath, params=params)
        if isinstance(res, dict) and 'snapshots' in res:
            return res['snapshots']
        elif isinstance(res, list):
            return res
        return []

    def wait_for_snapshot(self, snapshot_id, target_status='available', timeout=600, poll_interval=10, project_id=None):
        """
        Wait for a snapshot to reach a target status (default: 'available').
        """
        import time
        start_time = time.time()
        while time.time() - start_time < timeout:
            snap = self.get_snapshot(snapshot_id, project_id=project_id)
            status = snap.get('status', '').lower() if isinstance(snap, dict) else ''
            if status == target_status.lower():
                return snap
            elif status in ('error', 'failed'):
                error_msg = snap.get('error_msg') or snap.get('status_description') or 'Snapshot entered error state'
                self.module.fail_json(
                    msg="Snapshot '%s' failed with status '%s': %s" % (snapshot_id, status, error_msg),
                    snapshot=snap
                )
            time.sleep(poll_interval)

        self.module.fail_json(
            msg="Timeout waiting for snapshot '%s' to reach status '%s' after %d seconds." % (snapshot_id, target_status, timeout)
        )

    def delete_snapshot(self, snapshot_id, project_id=None):
        """
        Delete a snapshot by UUID (DELETE /v1/{project_id}/snapshots/{snapshot_id}).
        """
        target_project = project_id or self.project_id
        if not target_project:
            self.module.fail_json(msg="No OpenStack project ID available.")

        endpoint_has_project = bool(self.endpoint and (re.search(r'/[0-9a-fA-F]{32}', self.endpoint) or re.search(r'/[0-9a-fA-F-]{36}', self.endpoint)))
        if endpoint_has_project:
            subpath = '/snapshots/%s' % snapshot_id
        else:
            subpath = '/v1/%s/snapshots/%s' % (target_project, snapshot_id)

        return self.delete(subpath)



