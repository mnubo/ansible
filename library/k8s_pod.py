#!/usr/bin/python

# import module snippets
# import epdb
from ansible.module_utils.basic import *
from kubernetes import K8sConfig
from kubernetes import K8sPod
from kubernetes import K8sContainer
from kubernetes.exceptions.NotFoundException import NotFoundException

DOCUMENTATION = '''
---
module: k8s_pod
version_added: "1.9"
short_description: manages kubernetes pod objects
description:
     - Creates or deletes kubernetes pod objects.
options:
    annotations:
        description:
            - Kubernetes annotations to add to the replication controller.
    config:
        description:
            - A dictionary to configure the kubernetes module.
        default: dict(api_host='localhost:8888', namespace='default')
        required: False
    labels:
        description:
            - The labels to add to the replication controller. Should be a dictionary.
        default: 1
        required: False
    name:
        description:
            - Name of this replication controller. Will also generate a label with "name: name" for it.
        required: True
    spec:
        description:
            - An object describing the spec to create
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
    - name: Create a simple pod
      k8s_pod:
      config:
          api_host: "localhost:8888"
          namespace: "default"
          pull_secret: "my_registry"
      name: "myweb"
      spec:
          containers:
              - name: "myweb"
                image: "httpd:2.4"
                ports:
                  - containerPort: 80
                    hostPort: 31030
                    name: "tcp31030"
                    protocol: "TCP"
                env:
                  MY_VAR: "some_value"
                volumes:
                  - name: "my_volume"
                    mount_path: "/data/html"
                    read_only: False
          volumes:
              - type: "host"
                name: "my_volume"
                path: "/data/myweb/html"
      state: "present"
'''


def build_container(c):
    assert isinstance(c, dict)
    if 'name' in c.keys() and 'image' in c.keys():
        my_container = K8sContainer(name=c['name'], image=c['image'])
        try:
            if 'ports' in c.keys():
                my_ports = c.get('ports')
                assert isinstance(my_ports, list)
                for port in my_ports:
                    assert isinstance(port, dict)
                    container_port = port.get('containerPort', 65534)
                    host_port = port.get('hostPort', 65534)
                    protocol = port.get('protocol', 'TCP')
                    port_name = port.get('name', '{proto}{port}'.format(proto=protocol.lower(),
                                                                        port=str(host_port)))
                    if isinstance(container_port, str):
                        container_port = int(container_port)
                    if isinstance(host_port, str):
                        host_port = int(host_port)
                    my_container.add_port(container_port=container_port,
                                          host_port=host_port,
                                          name=port_name,
                                          protocol=protocol)
            if 'env' in c.keys():
                my_env = c.get('env')
                assert isinstance(my_env, dict)
                for my_k, my_v in my_env.iteritems():
                    my_container.add_env(k=my_k, v=my_v)
            if 'livenessProbe' in c.keys():
                my_probe = c.get('livenessProbe')
                assert isinstance(my_probe, dict)
                my_container.set_liveness_probe(**my_probe)
            if 'readinessProbe' in c.keys():
                my_probe = c.get('readinessProbe')
                assert isinstance(my_probe, dict)
                my_container.set_liveness_probe(**my_probe)
            if 'volumes' in c.keys():
                my_volumes = c.get('volumes')
                assert isinstance(my_volumes, list)
                for v in my_volumes:
                    if 'name' not in v.keys() or 'mount_path' not in v.keys():
                        raise SyntaxError('Please provide name and mount_path when defining a container volume')
                    if 'read_only' in v.keys():
                        my_container.add_volume_mount(name=v['name'],
                                                      mount_path=v['mount_path'],
                                                      read_only=v['read_only'])
                    else:
                        my_container.add_volume_mount(name=v['name'],
                                                      mount_path=v['mount_path'])
        except:
            raise
    else:
        raise SyntaxError('Please provide a name and an image for the container.')
    return my_container


def build_pod(config, pod_name, annotations=None, labels=None, spec=None):
    my_pod = K8sPod(config=config, name=pod_name)
    if annotations is not None:
        assert isinstance(annotations, dict)
        for my_k, my_v in annotations.iteritems():
            my_pod.add_annotation(k=my_k, v=my_v)
    if labels is not None:
        assert isinstance(labels, dict)
        for my_k, my_v in labels.iteritems():
            my_pod.add_label(k=my_k, v=my_v)
    if spec is not None:
        assert isinstance(spec, dict)
        if 'containers' in spec.keys():
            container_list = spec['containers']
            assert isinstance(container_list, list)
            for c in container_list:
                try:
                    my_container = build_container(c=c)
                    my_pod.add_container(container=my_container)
                except:
                    raise
        if 'volumes' in spec.keys():
            volume_list = spec['volumes']
            assert isinstance(volume_list, list)
            for v in volume_list:
                assert isinstance(v, dict)
                if 'type' not in v.keys():
                    raise SyntaxError('A volume type must be provided')
                if v['type'] == 'host':
                    my_pod.add_host_volume(name=v['name'], path=v['path'])
    return my_pod


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


def main():
    module = AnsibleModule(
        argument_spec=dict(
            annotations=dict(type='dict', default=None, required=False),
            config=dict(type='dict', default=dict(), required=False),
            labels=dict(type='dict', default=None, required=False),
            name=dict(type='str', required=True),
            spec=dict(type='dict', default=None, required=False),
            state=dict(type='str', required=True, choices=['absent', 'deleted', 'active', 'present'])
            ),
        supports_check_mode=True
    )
    # epdb.serve(port=8090)
    # Config parameters
    config = module.params.get('config')

    annotations = module.params.get('annotations')
    labels = module.params.get('labels')
    pod_name = module.params.get('name')
    spec = module.params.get('spec')
    requested_state = module.params.get('state')

    # Ansible variables
    ansible_output = dict(changed=False, data=None, msg='')

    my_cfg = K8sConfig(api_host=config.get('api_host', 'localhost:8888'), namespace=config.get('namespace', 'default'),
                       pull_secret=config.get('pull_secret', None))
    my_pod = K8sPod(config=my_cfg, name=pod_name)

    try:
        my_pod.get()
        found_pod = True
    except NotFoundException:
        found_pod = False
        pass

    if requested_state in ['absent', 'deleted']:
        ansible_output['state'] = 'absent'
        if found_pod:
            if module.check_mode:
                ansible_output['changed'] = True
                module.exit_json(changed=True)
            try:
                my_pod.delete()
            except Exception as e:
                ansible_output['msg'] = 'Delete failed with exception: {my_ex}'.format(my_ex=type(e))
                ansible_output['changed'] = False
                module.fail_json(**ansible_output)
            ansible_output['changed'] = True
            ansible_output['msg'] = 'Pod deleted.'
        else:
            ansible_output['changed'] = False
            ansible_output['msg'] = 'Pod not found.'
    elif requested_state in ['active', 'present']:
        ansible_output['state'] = 'present'
        if not found_pod:
            try:
                if module.check_mode:
                    ansible_output['msg'] = 'Would create pod {name}'.format(name=pod_name)
                    ansible_output['changed'] = True
                    module.exit_json(**ansible_output)
                else:
                    my_pod = build_pod(config=my_cfg, pod_name=pod_name, annotations=annotations,
                                       labels=labels, spec=spec)
                    my_pod.create()
                    ansible_output['changed'] = True
                    ansible_output['msg'] = 'Pod created.'
            except Exception as e:
                ansible_output['msg'] = 'Pod creation failed with exception ' \
                                        'type {my_ex} and message: {my_msg}'.format(my_ex=type(e), my_msg=e.message)
                ansible_output['changed'] = False
                module.fail_json(**ansible_output)
        else:
            if spec is not None:
                assert isinstance(spec, dict)
                if 'containers' in spec.keys():
                    new_pod = build_pod(config=my_cfg, pod_name=pod_name, annotations=annotations,
                                        labels=labels, spec=spec)

                    my_pod.del_pod_node_name()
                    current_annotations = my_pod.get_annotations()
                    if annotations is None and current_annotations is not None:
                        new_pod.set_annotations(new_dict=current_annotations)

                    state, my_ex_current, my_ex_new = compare_objects(a=my_pod.as_dict(), b=new_pod.as_dict())
                    if not state:
                        try:
                            my_pod.delete()
                            new_pod = build_pod(config=my_cfg, pod_name=pod_name, annotations=annotations,
                                                labels=labels, spec=spec)
                            new_pod.create()
                            ansible_output['changed'] = True
                            ansible_output['msg'] = 'Old Pod deleted, new Pod created.'
                        except Exception as e:
                            exception_type = e.message
                            ansible_output['changed'] = True
                            ansible_output['msg'] = 'Pod update failed. Exception message: {e}'\
                                .format(e=exception_type)
                            module.fail_json(**ansible_output)
                    else:
                        ansible_output['changed'] = False
                        ansible_output['msg'] = 'Pod is identical to current definition.'
                else:
                    ansible_output['changed'] = False
                    ansible_output['msg'] = 'Pod should have containers defined.'
                    module.fail_json(**ansible_output)
            else:
                ansible_output['msg'] = 'A pod should have its spec defined.'
                ansible_output['changed'] = False
                module.fail_json(**ansible_output)
    module.exit_json(**ansible_output)


main()
