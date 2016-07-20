#!/usr/bin/python

# import module snippets
# import epdb
from ansible.module_utils.basic import *
from kubernetes import K8sConfig
from kubernetes import K8sReplicationController
from kubernetes import K8sContainer
from kubernetes.exceptions.NotFoundException import NotFoundException

DOCUMENTATION = '''
---
module: k8s_rc
version_added: "1.9"
short_description: manages kubernetes replication controller objects.
description:
     - Creates or deletes kubernetes replication controller objects.
options:
    also_delete_pods:
        description:
            - Resize to 0 the number of replicas before sending in the delete when state is absent or deleted.
        default: False
        required: False
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
    pod:
        description:
            - An object describing the pod to create
        required: False
    replicas:
        description:
            - Number of replicas for this replication controller.
        default: 1
        required: False
    state:
        description:
            - The desired state for the object.
        required: True
        choices: ['absent','deleted','active','present']
    update_wait_seconds:
        description:
            - Number of seconds
        default: 10
        required: False
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
    k8s_rc:
      config:
          api_host: "localhost:8888"
          namespace: "default"
          pull_secret: "my_registry"
      name: "myweb"
      pod:
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
      replicas: 2
      state: "present"
'''


def build_container(c):
    # epdb.st()
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
                    host_port = port.get('hostPort', None)
                    protocol = port.get('protocol', 'TCP')
                    port_name = port.get('name', None)
                    if isinstance(container_port, str):
                        container_port = int(container_port)
                    if isinstance(host_port, str):
                        host_port = int(host_port)
                    my_container.add_port(container_port=container_port,
                                          host_port=host_port,
                                          name=port_name,
                                          protocol=protocol)
            if 'args' in c.keys():
                my_arguments = c.get('args')
                assert isinstance(my_arguments, list)
                my_container.set_arguments(args=my_arguments)
            if 'command' in c.keys():
                my_command = c.get('command')
                assert isinstance(my_command, list)
                my_container.set_command(cmd=my_command)
            if 'env' in c.keys():
                my_env = c.get('env')
                assert isinstance(my_env, dict)
                for my_k, my_v in my_env.iteritems():
                    my_container.add_env(k=my_k, v=my_v)
            if 'limits' in c.keys():
                my_limits = c.get('limits')
                assert isinstance(my_limits, dict)
                cpu_limit = my_limits.get('cpu', None)
                mem_limit = my_limits.get('memory', None)
                if cpu_limit is not None and mem_limit is not None:
                    my_container.set_limit_resources(cpu=cpu_limit, mem=mem_limit)
                else:
                    raise SyntaxError('Please define a CPU and a memory limit.')
            if 'livenessProbe' in c.keys():
                my_probe = c.get('livenessProbe')
                assert isinstance(my_probe, dict)
                my_container.set_liveness_probe(**my_probe)
            if 'readinessProbe' in c.keys():
                my_probe = c.get('readinessProbe')
                assert isinstance(my_probe, dict)
                my_container.set_readiness_probe(**my_probe)
            if 'requests' in c.keys():
                my_req = c.get('requests')
                assert isinstance(my_req, dict)
                my_container.set_requested_resources(cpu=my_req.get('cpu', '100m'), mem=my_req.get('memory', '32M'))
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


def build_replication_controller(config, rc_name, replicas, annotations=None, labels=None, pod=None):
    try:
        my_rc = K8sReplicationController(config=config, name=rc_name, replicas=replicas)
        # epdb.st()
        if annotations is not None:
            assert isinstance(annotations, dict)
            for my_k, my_v in annotations.iteritems():
                my_rc.add_annotation(k=my_k, v=my_v)
        if labels is not None:
            assert isinstance(labels, dict)
            for my_k, my_v in labels.iteritems():
                my_rc.add_label(k=my_k, v=my_v)
        if pod is not None:
            assert isinstance(pod, dict)
            if 'containers' in pod.keys():
                container_list = pod['containers']
                assert isinstance(container_list, list)
                for c in container_list:
                    try:
                        my_container = build_container(c=c)
                        my_rc.add_container(container=my_container)
                    except:
                        raise
            if 'labels' in pod.keys():
                label_list = pod.get('labels')
                if label_list is not None:
                    assert isinstance(label_list, dict)
                    current_label_list = my_rc.get_pod_labels()
                    current_label_list.update(label_list)
                    my_rc.set_pod_labels(new_dict=current_label_list)
            if 'volumes' in pod.keys():
                volume_list = pod['volumes']
                assert isinstance(volume_list, list)
                for v in volume_list:
                    assert isinstance(v, dict)
                    if 'type' not in v.keys():
                        raise SyntaxError('A volume type must be provided')
                    if v['type'] == 'host':
                        my_rc.add_host_volume(name=v['name'], path=v['path'])
                    elif v['type'] == 'emptydir':
                        my_rc.add_emptydir_volume(name=v['name'])
            if 'dns_policy' in pod.keys():
                if pod['dns_policy'] in ['Default', 'ClusterFirst']:
                    my_rc.set_dns_policy(policy=pod['dns_policy'])
                else:
                    raise SyntaxError('dns_policy must be Default or ClusterFirst.')
    except:
        raise
    return my_rc


def detect_image_latest(pod=None):
    result = False
    if pod is not None:
        pattern = re.compile('\:latest$')
        assert isinstance(pod, dict)
        if 'containers' in pod.keys():
            container_list = pod['containers']
            assert isinstance(container_list, list)
            for c in container_list:
                if pattern.match(c['image']):
                    result = True
                    break
    return result


def compare_objects(a, b):
    are_same = False
    ex_a = list()
    ex_b = list()

    assert type(a) == type(b)
    if isinstance(a, dict):
        if 'rc_version' in a.keys() and 'rc_version' in b.keys():
            a.pop('rc_version', None)
            b.pop('rc_version', None)
        if 'terminationGracePeriodSeconds' in a.keys():
            a.pop('terminationGracePeriodSeconds', None)
        if 'terminationGracePeriodSeconds' in b.keys():
            b.pop('terminationGracePeriodSeconds', None)
        if 'securityContext' in a.keys():
            a.pop('securityContext', None)
        if 'securityContext' in b.keys():
            b.pop('securityContext', None)
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
        if len(a) == len(b):
            for idx, val in enumerate(a):
                try:
                    result, result_a, result_b = compare_objects(a[idx], b[idx])
                    if not result:
                        ex_a.append(result_a)
                        ex_b.append(result_b)
                except IndexError:
                    ex_a.append(a[idx])
                    ex_b.append('')
                    pass
                except AssertionError:
                    ex_a.append(a[idx])
                    ex_b.append(b[idx])
                    pass
        else:
            ex_a.append(a)
            ex_b.append(b)
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
            also_delete_pods=dict(type='bool', default=False, required=False),
            annotations=dict(type='dict', default=None, required=False),
            config=dict(type='dict', default=dict(), required=False),
            labels=dict(type='dict', default=None, required=False),
            name=dict(type='str', required=True),
            pod=dict(type='dict', default=None, required=False),
            replicas=dict(type='int', default=1, required=False),
            update_wait_seconds=dict(type='int', default=10, required=False),
            state=dict(type='str', required=True, choices=['absent', 'deleted', 'active', 'present'])
        ),
        supports_check_mode=True
    )
    # epdb.serve(port=3000)
    # Config parameters
    config = module.params.get('config')

    # RC parameters
    also_delete_pods = module.params.get('also_delete_pods')
    annotations = module.params.get('annotations', None)
    labels = module.params.get('labels', None)
    pod = module.params.get('pod', None)
    rc_name = module.params.get('name', None)
    replicas = module.params.get('replicas', None)
    update_wait_seconds = module.params.get('update_wait_seconds')
    requested_state = module.params.get('state')

    # Ansible variables
    ansible_output = dict(changed=False, data=None, msg='')

    my_cfg = K8sConfig(api_host=config.get('api_host', 'localhost:8888'), namespace=config.get('namespace', 'default'),
                       pull_secret=config.get('pull_secret', None))
    my_rc = K8sReplicationController(config=my_cfg, name=rc_name)

    try:
        my_rc.get()
        found_rc = True
    except NotFoundException:
        found_rc = False
        pass

    if requested_state in ['absent', 'deleted']:
        ansible_output['state'] = 'absent'
        if found_rc:
            if module.check_mode:
                ansible_output['changed'] = True
                module.exit_json(**ansible_output)
            try:
                if also_delete_pods:
                    my_rc.set_replicas(replicas=0)
                    my_rc.update()
                    my_rc.wait_for_replicas(replicas=0)
                    ansible_output['msg'] += 'Resized the replication controller to 0. '
                my_rc.delete()
                rc_present = True
                while rc_present:
                    rc_list = my_rc.get_by_name(config=my_cfg, name=rc_name)
                    if len(rc_list) == 0:
                        rc_present = False
                    else:
                        time.sleep(0.2)
            except Exception as e:
                ansible_output['msg'] = 'Delete failed with exception: {my_msg}'.format(my_msg=e.message)
                ansible_output['changed'] = False
                module.fail_json(**ansible_output)
            ansible_output['changed'] = True
            ansible_output['msg'] += 'Replication controller deleted.'
        else:
            ansible_output['changed'] = False
            ansible_output['msg'] = 'Replication controller not found.'

    elif requested_state in ['active', 'present']:
        ansible_output['state'] = 'present'

        if not found_rc:
            try:
                if module.check_mode:
                    ansible_output['msg'] = 'Would create replication controller {name}'.format(name=rc_name)
                    ansible_output['changed'] = True
                    module.exit_json(**ansible_output)
                else:
                    my_rc = build_replication_controller(config=my_cfg, rc_name=rc_name, replicas=replicas,
                                                         annotations=annotations, labels=labels, pod=pod)
                    # epdb.st()
                    my_rc.create()
                    rc_exists = False
                    while not rc_exists:
                        try:
                            my_rc.get()
                            rc_exists = True
                        except NotFoundException:
                            time.sleep(0.3)
                            pass
                        except:
                            raise
                    my_rc.wait_for_replicas(replicas=replicas)
                    ansible_output['changed'] = True
                    ansible_output['msg'] = 'Replication controller created.'
            except Exception as e:
                ansible_output['msg'] = 'Replication controller creation failed with exception: {my_msg}' \
                    .format(my_msg=e.message)
                ansible_output['changed'] = False
                module.fail_json(**ansible_output)

        else:
            if pod is not None:
                assert isinstance(pod, dict)
                if 'containers' in pod.keys():
                    new_rc = build_replication_controller(config=my_cfg, rc_name=rc_name, replicas=replicas,
                                                          annotations=annotations, labels=labels, pod=pod)

                    labels = my_rc.get_pod_labels()
                    labels.pop('rc_version', None)
                    my_rc.set_labels(new_dict=labels)

                    selector = my_rc.get_selector()
                    selector.pop('rc_version', None)
                    my_rc.set_selector(selector=selector)

                    my_rc.set_pod_generate_name(mode=False, name=None)

                    labels = new_rc.get_pod_labels()
                    labels.pop('rc_version', None)
                    new_rc.set_labels(new_dict=labels)

                    selector = new_rc.get_selector()
                    selector.pop('rc_version', None)
                    new_rc.set_selector(selector=selector)

                    state, my_ex_current, my_ex_new = compare_objects(a=my_rc.as_dict(), b=new_rc.as_dict())
                    is_latest = detect_image_latest(pod=pod)
                    # epdb.st()
                    if (not state) or is_latest:
                        try:
                            K8sReplicationController.rolling_update(config=my_cfg, name=rc_name, new_rc=new_rc,
                                                                    wait_seconds=update_wait_seconds)
                            ansible_output['changed'] = True
                            ansible_output['exclusive_old'] = str(my_ex_current)
                            ansible_output['exclusive_new'] = str(my_ex_new)
                            ansible_output['msg'] = 'Replication controller updated.'
                        except Exception as e:
                            exception_type = e.message
                            ansible_output['changed'] = True
                            ansible_output['msg'] = 'Rolling restart failed. Exception message: {e}' \
                                .format(e=exception_type)
                            module.fail_json(**ansible_output)
                    else:
                        ansible_output['changed'] = False
                        ansible_output['msg'] = 'Replication controller is identical to current definition.'
                else:
                    ansible_output['changed'] = False
                    ansible_output['msg'] = 'Replication controller should have a pod with containers defined.'
                    module.fail_json(**ansible_output)
            else:
                ansible_output['msg'] = 'A replication controller should have a pod defined.'
                ansible_output['changed'] = False
                module.fail_json(**ansible_output)

    module.exit_json(**ansible_output)


main()
