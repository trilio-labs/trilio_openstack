#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

"""
Alias/forwarder module for workload_info.
Allows playbooks to invoke either `trilio_workload_info` or `workload_info`.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible_collections.trilio.trilio_openstack.plugins.modules.workload_info import (
    DOCUMENTATION,
    EXAMPLES,
    RETURN,
    main
)

if __name__ == '__main__':
    main()
