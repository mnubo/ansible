#!/usr/bin/python


# import module snippets
# import epdb
from ansible.module_utils.basic import *
from kubernetes import K8sConfig
from kubernetes import K8sService
from kubernetes.exceptions.NotFoundException import NotFoundException
from kubernetes.exceptions.UnprocessableEntityException import UnprocessableEntityException


DOCUMENTATION = '''
---
module: k8s_service
version_added: "1.9"
short_description: manages kubernetes service objects
description:
     - Creates or deletes kubernetes service objects.
options:
    config:
        description:
            - Configuration dictionary
        default: empty dict()
        required: False
    name:
        description:
            - Name of this service.
        required: True
    definition:
        description:
            - Definition of the service.
        required: False
    state:
        description:
            - The desired state for the object.
        required: True
        choices: ['absent','deleted','active','present']
requirements:
    - "python >= 2.6"
    - "kubernetes-py >= 0.16"
notes:
  - None now.
author: Sebastien Coutu <scoutu@mnubo.com>
'''

EXAMPLES = '''
# Basic example
#
      k8s_service:
        config:
            api_host: "{{ kube_master_ip }}:8888"
            namespace: "default"
        name: "myweb"
        definition:
          service_type: "NodePort"
          ports:
            - port: 31030
              target_port: "tcp31030"
              protocol: "TCP"
              node_port: 8030
          selector:
            name: "myweb"
          cluster_ip: "10.100.200.10"
        state: "present"
'''


def compare_objects(a, b):
    are_same = False
    ex_a = list()
    ex_b = list()

    assert type(a) == type(b)
    if isinstance(a, dict):
        if 'rc_version' in a.keys() and 'rc_version' in b.keys():
            a.pop('rc_version', None)
            b.pop('rc_version', None)
        keys_a = set(sorted(a.keys()))
        keys_b = set(sorted(b.keys()))
        if keys_a == keys_b:
            for key in (a.keys()):
                try:
                    result, result_a, result_b = compare_objects(a[key], b[key])
                    if not result:
                        ex_a.append({key: result_a})
                        ex_b.append({key: result_b})
                except AssertionError:
                    ex_a.append({key: a[key]})
                    ex_b.append({key: b[key]})
                    pass
        else:
            ex_a = keys_a - keys_b
            ex_b = keys_b - keys_a
    elif isinstance(a, list):
        for idx, val in enumerate(a):
            try:
                result, result_a, result_b = compare_objects(a[idx], b[idx])
                if not result:
                    ex_a.append(result_a)
                    ex_b.append(result_b)
            except AssertionError:
                ex_a.append(a[idx])
                ex_b.append(b[idx])
                pass
    elif isinstance(a, str) or isinstance(a, int) or isinstance(a, float) or isinstance(a, bool):
        if a != b:
            ex_a.append(a)
            ex_b.append(b)
    else:
        raise TypeError("I don't know about this type: {str}".format(str=type(a)))

    if len(ex_a) == 0 and len(ex_b) == 0:
        are_same = True

    return are_same, ex_a, ex_b


def build_service(config, service_name, service_definition, annotations, labels):
    my_svc = K8sService(config=config, name=service_name)
    assert isinstance(service_definition, dict)

    svc_type = service_definition.get('service_type', 'ClusterIP')
    my_svc.set_service_type(service_type=svc_type)

    affinity = service_definition.get('session_affinity', None)
    if affinity is not None:
        my_svc.set_session_affinity(affinity_type=affinity)

    if 'ports' not in service_definition.keys():
        raise SyntaxError('Missing the ports definition')

    ports = service_definition.get('ports')
    i = 0
    for port in ports:
        assert isinstance(port, dict)
        if 'port' in port.keys():
            my_port = port.get('port')
            target_port = port.get('target_port', None)
            node_port = port.get('node_port', None)

            if isinstance(my_port, str):
                assert isinstance(my_port, str)
                if my_port.isdigit():
                    my_port = int(my_port)
                else:
                    raise SyntaxError('port should be a number.')
            elif not isinstance(my_port, int):
                raise SyntaxError('port should be a number')

            if target_port is not None:
                if isinstance(target_port, str):
                    if target_port.isdigit():
                        target_port = int(target_port)
                        if target_port < 1 or target_port > 65535:
                            raise SyntaxError('target_port should between 1 and 65535')
                    else:
                        if len(target_port) > 15:
                            raise SyntaxError('target_port should not exceed 15 characters.')
                elif isinstance(target_port, int):
                    if target_port < 1 or target_port > 65535:
                        raise SyntaxError('target_port should between 1 and 65535')
                else:
                    raise SyntaxError('target_port should be a string (less than 15 chars) or an integer')

            if node_port is not None:
                if not isinstance(node_port, int):
                    node_port = int(node_port)

            my_svc.add_port(port=my_port,
                            name=port.get('name', None),
                            target_port=target_port,
                            protocol=port.get('protocol', None),
                            node_port=node_port)
        i += 1
    if 'selector' in service_definition.keys():
        selector = service_definition.get('selector')
        assert isinstance(selector, dict)
        my_svc.add_selector(selector=selector)

    if 'cluster_ip' in service_definition.keys():
        my_svc.set_cluster_ip(ip=service_definition.get('cluster_ip'))

    if annotations is not None:
        assert isinstance(annotations, dict)
        my_svc.set_annotations(new_dict=annotations)

    if labels is not None:
        assert isinstance(labels, dict)
        my_svc.set_labels(new_dict=labels)

    return my_svc


def main():
    module = AnsibleModule(
        argument_spec=dict(
            annotations=dict(type='dict', default=None, required=False),
            config=dict(type='dict', default=dict(), required=False),
            labels=dict(type='dict', default=None, required=False),
            name=dict(type='str', required=True),
            definition=dict(type='dict', default=dict(), required=False),
            state=dict(type='str', required=True, choices=['absent', 'deleted', 'active', 'present'])
            ),
        supports_check_mode=True
    )

    # Config parameters
    config = module.params.get('config')

    annotations = module.params.get('annotations')
    service_name = module.params.get('name')
    labels = module.params.get('labels')
    service_definition = module.params.get('definition')
    requested_state = module.params.get('state')

    # Ansible variables
    ansible_output = dict(changed=False, data=None, msg='')

    my_cfg = K8sConfig(api_host=config.get('api_host', 'localhost:8888'), namespace=config.get('namespace', 'default'))
    my_service = K8sService(config=my_cfg, name=service_name)

    try:
        my_service.get()
        found_service = True
    except NotFoundException:
        found_service = False
        pass

    if requested_state in ['absent', 'deleted']:
        ansible_output['state'] = 'absent'
        if found_service:
            if module.check_mode:
                ansible_output['changed'] = True
                ansible_output['msg'] = 'Would delete the service.'
                module.exit_json(**ansible_output)
            try:
                my_service.delete()
                svc_present = True
                while svc_present:
                    svc_list = my_service.get_by_name(config=my_cfg, name=service_name)
                    if len(svc_list) == 0:
                        svc_present = False
                    else:
                        time.sleep(0.2)
                ansible_output['changed'] = True
                ansible_output['msg'] = 'Deleted the service.'
            except Exception as e:
                ansible_output['msg'] = 'Service delete failed with exception: {my_msg}'\
                    .format(my_msg=e.message)
                ansible_output['changed'] = False
                module.fail_json(**ansible_output)
        else:
            ansible_output['changed'] = False
            ansible_output['msg'] = 'Service not found'
    elif requested_state in ['active', 'present']:
        if not found_service:
            if module.check_mode:
                ansible_output['changed'] = True
                ansible_output['msg'] = 'Would create the service.'
                module.exit_json(**ansible_output)
            my_service = build_service(config=my_cfg, service_name=service_name, service_definition=service_definition,
                                       annotations=annotations, labels=labels)
            service_created = False
            retry_counter = 0
            while not service_created:
                try:
                    my_service.create()
                    service_created = True
                except UnprocessableEntityException as e:
                    time.sleep(3)
                    retry_counter += 1
                    if retry_counter <= 10:
                        pass
                    else:
                        ansible_output['msg'] = 'Service creation failed with exception: {my_msg}'\
                            .format(my_msg=e.message)
                        ansible_output['json_sent'] = my_service.as_json()
                        ansible_output['changed'] = False
                        module.fail_json(**ansible_output)
                except Exception as e:
                    ansible_output['msg'] = 'Service creation failed with exception: {my_msg}'\
                        .format(my_msg=e.message)
                    ansible_output['json_sent'] = my_service.as_json()
                    ansible_output['changed'] = False
                    module.fail_json(**ansible_output)
            ansible_output['changed'] = True
            ansible_output['msg'] = 'Created service.'
        else:
            if module.check_mode:
                ansible_output['changed'] = True
                ansible_output['msg'] = 'Would update the service.'
                module.exit_json(**ansible_output)
            new_service = build_service(config=my_cfg, service_name=service_name, service_definition=service_definition,
                                        annotations=annotations, labels=labels)
            if service_definition.get('cluster_ip', None) is None:
                new_service.set_cluster_ip(ip=my_service.get_cluster_ip())
            old_resource_version = my_service.get_meta_resource_version()
            my_service.del_server_generated_meta_attr()
            state, my_ex_current, my_ex_new = compare_objects(a=my_service.as_dict(), b=new_service.as_dict())
            if not state:
                try:
                    my_service = new_service
                    my_service.set_meta_resource_version(ver=old_resource_version)
                    my_service.update()
                    ansible_output['changed'] = True
                    ansible_output['msg'] = 'Service updated.'
                except Exception as e:
                    ansible_output['msg'] = 'Service update failed with exception: {my_msg}'\
                        .format(my_msg=e.message)
                    ansible_output['changed'] = False
                    module.fail_json(**ansible_output)
            else:
                ansible_output['changed'] = False
                ansible_output['msg'] = 'Service definition is identical to current service.'

    module.exit_json(**ansible_output)


main()
