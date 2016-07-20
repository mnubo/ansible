#!/usr/bin/python


# import module snippets
# import epdb
from ansible.module_utils.basic import *
from kubernetes import K8sConfig
from kubernetes import K8sSecret
from kubernetes.exceptions.NotFoundException import NotFoundException


DOCUMENTATION = '''
---
module: k8s_secret
version_added: "1.9"
short_description: manages kubernetes secret objects
description:
     - Creates or deletes kubernetes secret objects.
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
      k8s_secret:
        config:
            api_host: "{{ kube_master_ip }}:8888"
            namespace: "default"
        name: "myregistry"
        definition:
          secret_type: "dockercfg"
          data: '{"dockerep-0.mtl.mnubo.com":{"auth":"bW51Ym9fZG9ja2VyOmRvY2tlcmZvcm1udWJvMTIz", "email":"analytics@mnubo.com"}}'
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


def build_secret(config, secret_name, definition):
    my_secret = K8sSecret(config=config, name=secret_name)
    assert isinstance(definition, dict)

    try:
        secret_type = definition.get('secret_type', None)
        if secret_type is None:
            raise SyntaxError('Please make sure to tell us what type of secret you are creating')

        my_data = definition.get('data', None)
        if isinstance(my_data, dict):
            my_data = json.dumps(my_data)
        if secret_type == 'dockercfg':
            my_secret.set_dockercfg_secret(data=my_data)
        elif secret_type == 'dockercfg_json':
            my_secret.set_dockercfg_json_secret(data=my_data)
    except:
        raise
    return my_secret


def main():
    module = AnsibleModule(
        argument_spec=dict(
            config=dict(type='dict', default=dict(), required=False),
            name=dict(type='str', required=True),
            definition=dict(type='dict', default=dict(), required=False),
            state=dict(type='str', required=True, choices=['absent', 'deleted', 'active', 'present'])
            ),
        supports_check_mode=True
    )
    # epdb.serve(port=8090)
    # Config parameters
    config = module.params.get('config')

    secret_name = module.params.get('name')
    secret_definition = module.params.get('definition')
    requested_state = module.params.get('state')

    # Ansible variables
    ansible_output = dict(changed=False, data=None, msg='')

    my_cfg = K8sConfig(api_host=config.get('api_host', 'localhost:8888'), namespace=config.get('namespace', 'default'))
    my_secret = K8sSecret(config=my_cfg, name=secret_name)

    try:
        my_secret.get()
        found_secret = True
    except NotFoundException:
        found_secret = False
        pass

    if requested_state in ['absent', 'deleted']:
        ansible_output['state'] = 'absent'
        if found_secret:
            if module.check_mode:
                ansible_output['changed'] = True
                ansible_output['msg'] = 'Would delete the secret.'
                module.exit_json(**ansible_output)
            my_secret.delete()
            ansible_output['changed'] = True
            ansible_output['msg'] = 'Deleted the secret.'
        else:
            ansible_output['changed'] = False
            ansible_output['msg'] = 'Secret not found'
    elif requested_state in ['active', 'present']:
        if not found_secret:
            if module.check_mode:
                ansible_output['changed'] = True
                ansible_output['msg'] = 'Would create the secret.'
                module.exit_json(**ansible_output)
            try:
                my_secret = build_secret(config=my_cfg, secret_name=secret_name, definition=secret_definition)
                # epdb.st()
                my_secret.create()
                ansible_output['changed'] = True
                ansible_output['msg'] = 'Created secret.'
            except Exception as e:
                ansible_output['changed'] = False
                ansible_output['msg'] = 'Failed to create service: {msg}'.format(msg=e.message)
                ansible_output['data'] = my_secret.as_json()
                module.fail_json(**ansible_output)
        else:
            if module.check_mode:
                ansible_output['changed'] = True
                ansible_output['msg'] = 'Would update the secret.'
                module.exit_json(**ansible_output)
            new_secret = build_secret(config=my_cfg, secret_name=secret_name, definition=secret_definition)
            state, my_ex_current, my_ex_new = compare_objects(a=my_secret.as_dict(), b=new_secret.as_dict())
            if not state:
                my_secret.delete()
                new_secret.create()
                ansible_output['changed'] = True
                ansible_output['msg'] = 'Secret updated. Old version deleted and new version created.'
            else:
                ansible_output['changed'] = False
                ansible_output['msg'] = 'Secret definition is identical to current secret.'

    module.exit_json(**ansible_output)


main()
