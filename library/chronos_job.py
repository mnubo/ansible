#!/usr/bin/python

import httplib
import dateutil.parser
import urllib

# import module snippets
from ansible.module_utils.basic import *

DOCUMENTATION = '''
---
module: chronos_job
version_added: "1.9"
short_description: manage chronos scheduled jobs.
description:
     - CRUD operations on chronos jobs.
options:
    chronos_hosts:
        description:
            - List of host on which chronos might be available.
        default: ['localhost']
        required: True
    port:
        description:
            - Port where the chronos server is listening.
        default:8080
        required: False
    name:
        description:
            - Name of job to manage.
        required: True
    description:
        description:
            - Human-readable description of chronos job.
        default: None
        required: False
    owner_email:
        description:
            - e-mail address to notify in case of failure.
        default: None
        required: False
    owner_name:
        description:
            - Human-readable format of job owner.
        default: None
        required: False
    env:
        description:
            - An array of environnment variable assignments that will be passed
              either to the mesos or docker executor back-end.
        default: None
        required: False
    constraints:
        description:
            - List of constraints which control where jobs run.
              Each constraint is compared against the attributes of a Mesos slave..
        default: None
        required: False
        TESTS TODO
    state:
        description:
            - Expected state of the job.
              created: scheduled as specified by other parameters
              disabled: job is registered, but not started
              asynchronous: for long-running jobs (see chronos documentation)
              deleted: remove the job from scheduler
              killed: stops all the job tasks: do _not_ remove job from scheduler
              started: immediately start the corresponding job task(s).
        default: created
        required: False
        choices: ['created','disabled','asynchronous','deleted','started','killed']
    command:
        description:
            - The command that will be executed by chronos.
        default: None
        required: False
    args:
        description: for state = 'created' or 'started' additional arguments to append to the jobs command
        default: None
        required: False
    runas_user:
        description:
            - The user mesos specifies when running the command
        default: Mesos default
        required: False
    retries:
        description:
            - If a job command fails, then retries this number of times before giving up.
        default: 2
        required: False
    repeat:
        description:
            - A number, stating how many time a job is supposed to repeat.
        default: 0 (which means infinite)
        required: False
        choices: ['created','asynchronous','deleted','started','killed']
    start_time:
        description:
            - When to start the job. Not providing this means that jobs starts immediately.
              Otherwise, should be specified in ISO 8601 format, i.e. YYYY-MM-DDThh:mm:ss.sTZD
        default: None
        required: False
    start_tz:
        description:
            - the time zone to use when scheduling the job, overriding the one given
              in start_time
        default: None
        required: False
    run_interval:
        description:
            - Interval between each runs, specified as a duration in ISO 8601 format.
        default: None
        required: False, mandatory if parent_job is not present
    epsilon:
        description:
            - tolerated error marging if chronos misses the start time for any reason.
              It must be formatted like an ISO8601 Duration.
        default: PT60S
        required: False
    parents:
        description:
            - List of parent job names: this job will only run if all of its parent have been
              triggered once.
        default: None
        required: False, mutually excluse with all other time-based scheduling parameters
        TEST TODO
    cpus:
        description:
            - amount of cpu requested to mesos.
        default: None
        required: False
    mem:
        description:
            - amount of memory in MB requested to mesos.
        default: None
        required: False
    disk:
        description:
            - amount of disk space in MB requested to mesos.
        default: None
        required: False
    docker_image:
        description:
            - When the job is executed  within a docker container,
              then the image name should be provided.
        default: None
        required: False
    docker_network:
        description:
            - When the job is executed  within a docker container, this gives the
              type of the network binding.
        required: False
        choices: ['BRIDGE','NONE','HOST','CONTAINER:<ANOTHER_CONTAINER_NAME_OR_ID>']
    docker_volumes:
        description:
            - When the job is executed  within a docker container, this gives the
              volumes to mount in the container.
        required: False
        format: same as for ansible docker module
    docker_pull:
        description:
            - image-pulling behavior, same syntax and semantic as ansible docker 'pull' argument
        default: 'missing'
        required: False
        choices: ['missing', 'always']

requirements:
    - "python >= 2.6"
notes:
  - None now.
author: Bruno Hivert <bhivert@mnubo.com>
'''

EXAMPLES = '''
# Basic example
#
---
# file: sample-chronos-job-schedule.yml
- hosts:
    - mesos-masters
  tasks:
    - name: Schedule sample-chronos-job
      chronos_job:
        chronos_hosts: "{{ groups['mesos-masters'] }}"
        port: 4400
        name: "sample-chronos-job"
        state: created
        start_time: "2015-11-11T00:00:00Z"
        run_interval: "P1D"
        epsilon: "PT6H"
        cpus: 1.0
        mem: 1024
        docker_image: "{{ docker_registry }}/sample-chronos-job:{{ sample_chronos_job_version }}"
        env: ["ENV={{ env_id }}","JAVA_OPTS=-Xmx512m -Xms512m"]
        owner_email: "{{ chronos_job_alert_email }}"
        uris: "{{ chronos_docker_cred_uri }}"
      run_once: true
      delegate_to: "{{ groups['mesos-masters'][0] }}"
---
# file: sample-chronos-job-run.yml
- hosts:
    - mesos-masters
  tasks:
    - name: Start sample-job on Chronos
      chronos_job:
        chronos_hosts: "{{ groups['mesos-masters'] }}"
        port: 4400
        name: "sample-chronos-job"
        state: "started"
      run_once: true
      delegate_to: "{{ groups['mesos-masters'][0] }}"
      register: chrono_job_debug
---
# file: sample-chronos-job-unschedule.yml

- hosts:
    - mesos-masters
  tasks:
    - name: Kill sample-chronos-job
      chronos_job:
        chronos_hosts: "{{ groups['mesos-masters'] }}"
        port: 4400
        name: "sample-chronos-job"
        state: killed
      run_once: true
      delegate_to: "{{ groups['mesos-masters'][0] }}"

    - name: Delete sample-chronos-job
      chronos_job:
        chronos_hosts: "{{ groups['mesos-masters'] }}"
        port: 4400
        name: "sample-chronos-job"
        state: deleted
      run_once: true
      delegate_to: "{{ groups['mesos-masters'][0] }}"
'''

#############################################################
#############################################################
###############     chronos_common.py    #####################
#############################################################
#############################################################


# chronos_job module.
# Common functions to rest-client modules.
# TODO: Ansible provide a way to auto-include required fields, look into it
# See class ModuleReplacer in module_common.py, there might be something there

SCHED_BASE_URL = '/scheduler/'


def my_http_request(method, host, port, url, payload):
    if method in ['PUT', 'POST']:
        headers = {"Accept": "application/json", "Content-type": "application/json"}
    else:
        headers = {"Accept": "application/json"}

    conn = httplib.HTTPConnection(host, port)
    if payload is None:
        conn.request(method, url)
    else:
        json_encoded = json.dumps(payload)
        conn.request(method, url, json_encoded, headers)

    response = conn.getresponse()
    status = response.status
    reason = response.reason

    data = response.read().decode('utf-8')

    if status in [200, 201, 204]:
        if len(data) > 0:
            data = json.loads(data)

    message = 'Chronos API status code is ' + str(status)

    conn.close()

    return status, data, message


def list_objects(api_host, api_port):
    # TODO: put a retry mechanism
    # when a connection fail to any element of the list
    api_url = SCHED_BASE_URL + 'jobs'
    (status, data, message) = my_http_request("GET", api_host[0], api_port, api_url, None)
    state = False
    if status is 200:
        state = True
    return state, data


def create_object(api_host, api_port, api_url, payload):
    (status, data, message) = my_http_request("POST", api_host[0], api_port, api_url, payload)
    state = False
    if status is 204:
        state = True
    return state, data


def update_object(api_host, api_port, api_url, payload):
    (status, data, message) = my_http_request("PUT", api_host[0], api_port, api_url, payload)
    state = False
    if status is 204:
        state = True
    return state, data


def delete_object(api_host, api_port, api_url, payload):
    (status, data, message) = my_http_request("DELETE", api_host[0], api_port, api_url, payload)
    state = False
    if status is 204:
        state = True
    return state, data


#############################################################
#############################################################
################     chronos_job.py     #####################
#############################################################
#############################################################

# chronos_job - a module for managing chronos jobs.

# This checks that parameter might be valid for the creation of a job
# case: created and and aysnchronous

# According to https://en.wikipedia.org/wiki/ISO_8601#Durations
# We have to match
# PnYnMnDTnHnMnS
# or
# PnW
ISO8601_DURATION_RE = re.compile('^P(\d+Y)?(\d+M)?(\d+D)?(T(\d+H)?(\d+M)?(\d+S)?)?$')  # HODOR !
ISO8601_WEEK_DURATION_RE = re.compile('^P(\d+W)$')


def validate_iso8601_duration(duration):
    return ISO8601_DURATION_RE.match(duration) or ISO8601_WEEK_DURATION_RE.match(duration)


def validate_params_creation(module):
    # Intermediate variables for code reading simplification:
    job_name = module.params.get('name')
    start_time = module.params.get('start_time')
    run_interval = module.params.get('run_interval')
    epsilon = module.params.get('epsilon')

    # Required by the chronos API
    if not module.params.get('owner_email'):
        module.fail_json(
            changed=False,
            msg='Job "%s" creation required non-empty "owner_email" parameter, please correct.' % job_name
        )

    # they are two main type of jobs:
    # - Scheduled job
    # - Dependent job
    if start_time or run_interval:

        # parameter mutual exclusion
        if module.params.get('parents'):
            module.fail_json(
                changed=False,
                msg='Job "%s" cannot be both scheduled _and_ dependant.' % job_name
            )

        # Schedule parameter validation not already done by AnsibleModule
        # Because chronos answers 400 without ANY error message
        try:
            dateutil.parser.parse(start_time)
        except ValueError:
            module.fail_json(
                changed=False,
                msg='Job "%s" start_time parameter "%s" is not valid, please correct.' % (job_name, start_time)
            )

        if not validate_iso8601_duration(run_interval):
            module.fail_json(
                changed=False,
                msg='Job "%s" run_interval parameter "%s" is not valid, please correct.' % (job_name, run_interval)
            )

        if epsilon and not validate_iso8601_duration(epsilon):
            module.fail_json(
                changed=False,
                msg='Job "%s" epsilon parameter "%s" is not valid, please correct.' % (job_name, epsilon)
            )

    return True


# Help building the dictionary which will eventually be translated to json
# module is an AnsibleModule object
# payload is a dictionary
# In order to ease function call, if param_name is not passed, it assumes
# param_name = payload_param_name
def add_param_if_exist(module, payload, payload_param_name, param_name=None):

    if not param_name:
        param_name = payload_param_name

    if module.params.get(param_name):
        payload[payload_param_name] = module.params.get(param_name)


def build_creation_dict(module):
    ret_dict = {
        'name': module.params.get('name')
    }

    # Generic parameters
    add_param_if_exist(module, ret_dict, 'description')
    add_param_if_exist(module, ret_dict, 'ownerName', 'owner_name')
    add_param_if_exist(module, ret_dict, 'owner', 'owner_email')
    add_param_if_exist(module, ret_dict, 'runAsUser', 'runas_user')
    add_param_if_exist(module, ret_dict, 'retries')
    add_param_if_exist(module, ret_dict, 'cpus')
    add_param_if_exist(module, ret_dict, 'mem')
    add_param_if_exist(module, ret_dict, 'disk')

    if module.params.get('state') == 'disabled':
        ret_dict['disabled'] = True

    # they are two main type of jobs:
    # - Scheduled job
    # - Dependent job
    # A job can be asynchronous or not (default)
    # And a job can be run through a command or docker

    # Scheduled job case - might have to adapt test
    if module.params.get('start_time'):
        # Build schedule
        if module.params.get('repeat'):
            schedule = 'R' + str(module.params.get('repeat')) + '/'
        else:
            schedule = 'R/'  # repeat ad infinitum
        schedule += module.params.get('start_time') + '/'
        schedule += module.params.get('run_interval')  # P is specified in documentation
        ret_dict['schedule'] = schedule
        add_param_if_exist(module, ret_dict, 'epsilon')
        add_param_if_exist(module, ret_dict, 'scheduleTimeZone', 'start_tz')

    # Dependent job add parents
    add_param_if_exist(module, ret_dict, 'parents')
    # Is this job an asynchronous one ?
    if module.params.get('state') == 'asynchronous':
        ret_dict['async'] = True

    # This is a command-driven job
    add_param_if_exist(module, ret_dict, 'command')
    add_param_if_exist(module, ret_dict, 'arguments', 'args')

    # Or this is a docker job: we need to construct another dictionary
    if module.params.get('docker_image'):
        docker_dict = {
            'type': 'DOCKER',
            'image': module.params.get('docker_image')
        }

        if module.params.get('always'):
            docker_dict['forcePullImage'] = True
            # We do not care about the missing case, this is False by default
        # TODO: add some keyword validation here
        add_param_if_exist(module, docker_dict, 'network', 'docker_network')

        if module.params.get('volumes'):
            vol_array = []
            # We asked the user to use the docker command-line format
            # /hostpath[:/containerPath[:rw or ro]]
            # but the chronos API asks for volumes as an array of dicts
            # (just to make it a bit more complicated !)
            # Do the transformation
            for vol_spec in module.params.get('volumes'):
                spec_dict = {}
                spec_array = vol_spec.split(":")
                spec_dict['hostPath'] = spec_array[0]
                if len(spec_array) >= 3:
                    module.fail_json(
                        changed=False,
                        msg='Bad volume specification: "%s", too many ":"' % vol_spec)
                elif len(spec_array) >= 2:
                    if spec_array[1]:
                        spec_dict['containerPath'] = spec_array[1]
                    if len(spec_array) >= 3 and spec_array[2]:
                        spec_dict['mode'] = spec_array[2].upper()  # UPPERCASE for chronos
                if spec_dict:  # is not empty
                    vol_array.append(spec_dict)
            docker_dict['volumes'] = vol_array

        ret_dict['container'] = docker_dict
        if 'command' not in ret_dict:
            ret_dict['command'] = '' # Dummy but mandatory argument passed to executable when shell = false for docker https://github.com/mesos/chronos/issues/341
        ret_dict['shell'] = False

    # the environment is specified the same way whether it's a command/docker job
    # Like with the volumes specification, we decided to avoid deviating from the
    # other module syntax: we now pay the parsing price
    if module.params.get('env'):
        env_vars = []
        for env_spec in module.params.get('env'):
            env_spec_dict = {}
            (name, value) = env_spec.split('=')
            env_spec_dict['name'] = name
            env_spec_dict['value'] = value
            env_vars.append(env_spec_dict)

        ret_dict['environmentVariables'] = env_vars

    # An array of URIs which Mesos will download when the task is started.
    add_param_if_exist(module, ret_dict, 'uris')

    return ret_dict


#############################################################
#############################################################
#############################################################
#############################################################

def main():
    module = AnsibleModule(
        argument_spec=dict(
            chronos_hosts=dict(required=True, type='list'),
            port=dict(required=False, type='int', default=8080),
            name=dict(required=True, type='str'),
            description=dict(required=False, type='str'),
            owner_email=dict(required=False, type='str'),
            owner_name=dict(required=False, type='str'),
            env=dict(required=False, type='list'),
            constraints=dict(required=False, type='list'),
            state=dict(required=True, choices=['created', 'disabled', 'asynchronous', 'deleted', 'killed', 'started']),
            command=dict(required=False, type='str'),
            args=dict(required=False, type='str'),
            runas_user=dict(required=False, type='str'),
            retries=dict(required=False, type='int'),  # default as documented by current chronos version
            repeat=dict(required=False, type='int'),
            start_time=dict(required=False, type='str'),
            start_tz=dict(required=False, type='str'),
            run_interval=dict(required=False, type='str'),
            epsilon=dict(required=False, type='str'),
            parents=dict(required=False, type='list'),
            cpus=dict(required=False, type='float'),
            mem=dict(required=False, type='int'),
            disk=dict(required=False, type='int'),
            docker_image=dict(required=False, type='str'),
            docker_network=dict(required=False, type='str'),
            docker_volumes=dict(required=False, type='list'),
            docker_pull=dict(required=False, default='missing', choices=['missing', 'always']),
            uris=dict(required=False, type='list')
        ),
        supports_check_mode=False  # TODO eventually
    )

    api_host_list = module.params.get('chronos_hosts')
    api_port = module.params.get('port')
    name = module.params.get('name')
    target_state = module.params.get('state')

    # Note:
    # required=True argument checking is done by the ansible module library
    # the other consistency checks are done depending on target_state parameter

    if target_state in ['created', 'asynchronous', 'disabled']:
        # Validate that the set of arguments is sufficient for the created state
        validate_params_creation(module)
        payload = build_creation_dict(module)
        # different endpoints depending on a scheduled job or dependent job
        if module.params.get('start_time'):
            api_url = SCHED_BASE_URL + 'iso8601'
        else:
            api_url = SCHED_BASE_URL + 'dependency'

        (ok, data) = create_object(api_host_list, api_port, api_url, payload)

        # POSSIBLE IMPROVEMENT
        # call to list_object() here to validate the job was really scheduled.

        if ok:
            module.exit_json(
                changed=True,
                returned_data=data,
                sent_json_payload=payload,
                msg='Chronos job "%s" created OK' % name
            )
        else:
            module.fail_json(
                changed=False,
                msg=data,
                sent_json_payload=payload
            )

    # All other operations code below require an already existing job
    # Does it exist ?
    job_state = None
    ret_code = False
    job_list = []  # The Chronos api returns an array of dicts
    # one dict = one job

    (ret_code, job_list) = list_objects(api_host_list, api_port)

    if ret_code:
        for job in job_list:
            # That won't scale well if they are too many jobs, but hey...
            if name == job['name']:
                job_state = job
                break
    else:
        module.fail_json(
            changed=False,
            msg='Cannot get Chronos job list, was searching for name "%s"' % name
        )

    if target_state == 'deleted':
        if not job_state:
            # job was not found, nothing to do
            module.exit_json(
                changed=False,
                msg='Chronos job "%s" is already deleted or absent' % name
            )

        # Must do it
        (ret_code, ignored) = delete_object(api_host_list, api_port, SCHED_BASE_URL + 'job/' + name, None)
        if ret_code:
            module.exit_json(
                changed=True,
                msg='Chronos job "%s" successfully deleted' % name
            )
        else:
            module.fail_json(
                changed=False,
                msg='Unable to delete Chronos job "%s", API returned an error.' % name
            )

    elif target_state == 'killed':
        # This requires an already existing job
        if not job_state:
            module.fail_json(
                changed=False,
                msg='Unable to find Chronos job name "%s", cannot kill tasks' % name
            )

        (ret_code, ignored) = delete_object(api_host_list, api_port, SCHED_BASE_URL + 'task/kill/' + name, None)
        if ret_code:
            module.exit_json(
                changed=True,
                msg='Chronos job "%s" tasks successfully killed' % name
            )
        else:
            module.fail_json(
                changed=False,
                msg='Unable to delete Chronos job "%s", API returned an error.' % name
            )

    elif target_state == 'started':
        if not job_state:
            # job was not found, ERROR
            module.fail_json(
                changed=False,
                msg='Chronos job "%s" does not exist' % name
            )

        url = SCHED_BASE_URL + 'job/' + name
        if module.params.get('args'):
            # Now we need to URL-encode the argument list, we assume...
            url += '?arguments=' + urllib.quote(module.params.get('args'))

        (ret_code, data) = update_object(api_host_list, api_port, url, None)
        if ret_code:
            module.exit_json(
                changed=True,
                api_response=data,
                msg='Chronos job "%s" tasks successfully started' % name
            )
        else:
            module.fail_json(
                changed=False,
                msg='Unable to start Chronos job "%s", API returned an error.' % name
            )

    # If execution reaches here, that's BAD
    # Do our best to help debug the problem...
    module.fail_json(
        changed=False,
        msg='Internal error in ansible module chronos_job',
        parameters=module.params
    )


if __name__ == '__main__':
    main()
