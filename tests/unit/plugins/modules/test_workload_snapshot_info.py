# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot_info import run_module


class TestWorkloadSnapshotInfoModule(unittest.TestCase):

    def test_query_snapshot_info(self):
        mock_module = MagicMock()
        mock_module.params = {
            'workload': 'my-workload',
            'snapshot': 'latest',
            'all_snapshots': False,
            'project_id': None,
        }

        mock_snap = {
            'id': 'snap-uuid-1',
            'name': 'snap-1',
            'instances': [{
                'name': 'vm-1',
                'nics': [{
                    'network': {
                        'id': 'net-uuid-1',
                        'name': 'net-1',
                        'subnet': {'name': 'sub-1', 'id': 'sub-uuid-1', 'cidr': '10.0.0.0/24'}
                    }
                }]
            }],
        }

        mock_client = MagicMock()
        mock_client.resolve_snapshot.return_value = mock_snap

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot_info.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot_info.TrilioClient', return_value=mock_client):
                run_module()

                mock_module.exit_json.assert_called_once()
                kwargs = mock_module.exit_json.call_args[1]
                self.assertFalse(kwargs['changed'])
                self.assertEqual(kwargs['discovered_instances'], ['vm-1'])
                self.assertEqual(kwargs['discovered_networks'], ['net-1'])
                self.assertEqual(len(kwargs['snapshots']), 1)


if __name__ == '__main__':
    unittest.main()
