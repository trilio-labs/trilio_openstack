# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.trilio.trilio_openstack.plugins.modules.workload_reassign import run_module


class TestWorkloadReassignModule(unittest.TestCase):

    def test_reassign_success(self):
        mock_module = MagicMock()
        mock_module.params = {
            'workload': 'test-workload',
            'workload_ids': None,
            'workload_name': None,
            'target_project': 'target-project-uuid',
            'target_user': 'target-user-uuid',
            'source_project': None,
            'source_btt': None,
            'target_btt': None,
            'migrate_storage': False,
        }
        mock_module.check_mode = False

        mock_client = MagicMock()
        mock_client.find_project_id.return_value = 'target-project-uuid'
        mock_client.find_user_id.return_value = 'target-user-uuid'
        mock_client.reassign_workloads.return_value = {
            'workloads': [{'id': 'wl-uuid-1', 'name': 'test-workload'}]
        }

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_reassign.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_reassign.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.reassign_workloads.assert_called_once()
                mock_module.exit_json.assert_called_once()
                kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(kwargs['changed'])
                self.assertEqual(kwargs['target_project_id'], 'target-project-uuid')
                self.assertEqual(kwargs['target_user_id'], 'target-user-uuid')

    def test_reassign_check_mode(self):
        mock_module = MagicMock()
        mock_module.params = {
            'workload': 'test-workload',
            'workload_ids': None,
            'workload_name': None,
            'target_project': 'target-project-uuid',
            'target_user': 'target-user-uuid',
            'source_project': None,
            'source_btt': None,
            'target_btt': None,
            'migrate_storage': False,
        }
        mock_module.check_mode = True

        mock_client = MagicMock()
        mock_client.find_project_id.return_value = 'target-project-uuid'
        mock_client.find_user_id.return_value = 'target-user-uuid'

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_reassign.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_reassign.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.reassign_workloads.assert_not_called()
                mock_module.exit_json.assert_called_once()
                kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(kwargs['changed'])


if __name__ == '__main__':
    unittest.main()
