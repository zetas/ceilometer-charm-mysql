Overview
--------

This charm provides the Ceilometer service for OpenStack.  It is intended to
be used alongside the other OpenStack components, starting with the Folsom
release.

Ceilometer is made up of 2 separate services: an API service, and a collector
service. This charm allows them to be deployed in different combination,
depending on user preference and requirements.

This charm was developed to support deploying Folsom on both Ubuntu Quantal
and Ubuntu Precise.  Since Ceilometer is only available for Ubuntu 12.04 via
the Ubuntu Cloud Archive, deploying this charm to a Precise machine will by
default install Ceilometer and its dependencies from the Cloud Archive.

Usage
-----

In order to deploy Ceilometer service, the MongoDB service is required:

    juju deploy mongodb
    juju deploy ceilometer
    juju add-relation ceilometer mongodb

then Keystone and Rabbit relationships need to be established:

    juju add-relation ceilometer rabbitmq
    juju add-relation ceilometer keystone:identity-service
    juju add-relation ceilometer keystone:identity-notifications

In order to capture the calculations, a Ceilometer compute agent needs to be
installed in each nova node, and be related with Ceilometer service:

    juju deploy ceilometer-agent
    juju add-relation ceilometer-agent nova-compute
    juju add-relation ceilometer:ceilometer-service ceilometer-agent:ceilometer-service

Ceilometer provides an API service that can be used to retrieve
Openstack metrics.
