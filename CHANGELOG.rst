======================================
Trilio.Trilio\_Openstack Release Notes
======================================

.. contents:: Topics

v1.0.1
======

Release Summary
---------------

Release 1.0.1 of the ``trilio.trilio_openstack`` collection, introducing cross-tenant workload reassignment and detailed snapshot network topology discovery for migration, rollback, and cleanup workflows.

Major Changes
-------------

- workload_reassign - Reassign ownership of one or more Trilio workloads and backup snapshot chains across OpenStack tenants and users.
- workload_snapshot_info - Retrieve detailed snapshot metadata, protected instances, and discover restored network topology (networks, subnets, CIDRs).

New Modules
-----------

- trilio.trilio_openstack.trilio_workload_reassign - Reassign Trilio for OpenStack workloads to a new tenant/user.
- trilio.trilio_openstack.trilio_workload_snapshot_info - Retrieve detailed information and network topology from Trilio for OpenStack workload snapshots.
- trilio.trilio_openstack.workload_reassign - Reassign Trilio for OpenStack workloads to a new tenant/user.
- trilio.trilio_openstack.workload_snapshot_info - Retrieve detailed information and network topology from Trilio for OpenStack workload snapshots.

v1.0.0
======

Release Summary
---------------

Initial release of the ``trilio.trilio_openstack`` collection, providing enterprise backup and recovery automation for Trilio for OpenStack (Workload Manager) and Red Hat OpenStack Services on OpenShift (RHOSO).

Major Changes
-------------

- backup_target - Manage NFS and S3 backup targets with dynamic mount management via Trilio 6.2+ Data Mover Service (DMS).
- backup_target_info - Query and discover backup targets and linked Backup Target Types (BTT).
- workload - Create, update, and manage protected OpenStack application workloads, instance memberships, and snapshot schedules.
- workload_info - List and inspect workloads, project protection coverage, and snapshot history with S3 bucket and target filters.
- workload_restore - Perform One-Click, In-Place, and Selective restores of workloads, virtual machines, and storage volumes.
- workload_snapshot - Trigger on-demand incremental and full baseline backups of protected workloads with synchronous waiting.

New Modules
-----------

- trilio.trilio_openstack.trilio_workload_info - Retrieve information about Trilio for OpenStack workloads.
- trilio.trilio_openstack.workload_info - Retrieve information about Trilio for OpenStack workloads.
