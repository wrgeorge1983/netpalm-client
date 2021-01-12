import json
from netpalm_client import NetpalmClient


NETPALM_URL = 'http://netpalm.example.org'  # URL to your internal Netpalm Instance
NETPALM_API_KEY = 'abc-123-xyz'  # API Key from your internal instance.  You're not using the default of "2a84465a-cf38-46b2-9d86-b84Q7d57f288" are you?!?

# please don't tell anyone I told you it's okay to do stuff like this
CLI_USERNAME = 'automation'  # creds Netpalm will use to authenticate to the device
CLI_PASSWORD = 'hunter2'

GOOD_HOSTS = [
    '192.168.0.1',
    '192.168.0.2'
]
BAD_HOSTS = [
    'dnsresolutionfailure.please',
    '127.0.10.10'
]


def single_example():
    host = GOOD_HOSTS[0]
    command = 'show run | i bgp router-id'

    netpalm = NetpalmClient(NETPALM_URL, NETPALM_API_KEY, CLI_USERNAME, CLI_PASSWORD)

    task_start_result = netpalm.netmiko_getconfig(command, host, 'cisco_ios')  # returns output like: https://public.netpalm.apcela.net/#/default/get_config_netmiko_getconfig_netmiko_post

    task_id = task_start_result['task_id']
    print(f'Got Task ID: {task_id}')


    print(json.dumps(task_start_result, indent=2))

    netpalm_result = netpalm.poll_task(task_id)  # poll that task_id until it's complete, return a result
    print(f'Got Result:')
    print(json.dumps(netpalm_result, indent=2))

    final_result = netpalm_result['task_result'][command] 
    print(f'Got this final result: {final_result}')



def multi_example():
    hosts = GOOD_HOSTS

    command = 'show run | i bgp router-id'

    netpalm = NetpalmClient(NETPALM_URL, NETPALM_API_KEY, CLI_USERNAME, CLI_PASSWORD)

    # Kick off all tasks so Netpalm can get started
    host_to_tasks = {}
    tasks_to_hosts = {}
    for host in hosts:
        task_id_dict = netpalm.netmiko_getconfig(command, host, 'cisco_ios', poison=True)
        task_id = task_id_dict['task_id']
        # We need to keep track of which task_id maps to which host, and vice versa
        host_to_tasks[host] = task_id
        tasks_to_hosts[task_id] = host
        print(f'got {host}: {task_id=}')

    task_ids = list(host_to_tasks.values())  # also handy to have a flat list of the task_ids.

    multi_result = netpalm.poll_tasks(task_ids)  # returns {task_id: result, task_id2: result2, ...}
    final_results = {}
    for task_id, result_dict in multi_result.items():
        final_result = result_dict['task_result'][command]
        host = tasks_to_hosts[task_id]
        final_results[host] = final_result

    for host, final_result in final_results.items():
        print(f'got result for {host}: \n {final_result}')


def error_example():
    hosts = BAD_HOSTS + GOOD_HOSTS[0:1]

    command = 'show run | i bgp router-id'

    netpalm = NetpalmClient(NETPALM_URL, NETPALM_API_KEY, CLI_USERNAME, CLI_PASSWORD)

    # Kick off all tasks so Netpalm can get started
    host_to_tasks = {}
    tasks_to_hosts = {}
    for host in hosts:
        task_id_dict = netpalm.netmiko_getconfig(command, host, 'cisco_ios', poison=True)
        task_id = task_id_dict['task_id']
        # We need to keep track of which task_id maps to which host, and vice versa
        host_to_tasks[host] = task_id
        tasks_to_hosts[task_id] = host
        print(f'got {host}: {task_id=}')

    task_ids = list(host_to_tasks.values())  # also handy to have a flat list of the task_ids.

    multi_result = netpalm.poll_tasks(task_ids)  # returns {task_id: result, task_id2: result2, ...}
    final_results = {}
    for task_id, result_dict in multi_result.items():
        host = tasks_to_hosts[task_id]
        try:
            final_result = result_dict['task_result'][command]
            
        except (KeyError, TypeError):
            print(json.dumps(result_dict, indent=2))
            print(f'Got error for host {host}: {result_dict["task_errors"]}')
            final_result = result_dict['task_errors']

        final_results[host] = final_result
    
    for host, final_result in final_results.items():
        print(f'got result for {host}: \n {final_result}')


if __name__ == '__main__':
    single_example()
    multi_example()
    error_example()
