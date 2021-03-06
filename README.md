# Netpalm-Client

Simple client library for working with [Netpalm](https://github.com/tbotnz/netpalm)

Detailed example available in [examples](https://github.com/wrgeorge1983/netpalm-client/tree/master/example) folder of this repo


## Install
```
pip install netpalm-client
```

## Basic Usage
```python
from netpalm_client import NetpalmClient

netpalm = NetpalmClient(
    url='https://netpalm.example.org',
    key='someApiKey',
    cli_user='cisco',
    cli_pass='cisco'
)

task_id = netpalm.netmiko_getconfig(
    command='show run | i bgp router-id',
    host='192.168.0.1'
)['task_id']

netpalm_result = netpalm.poll_task(task_id)  # blocks until polling returns either completion or failure

actual_result = netpalm_result['task_result'][command]  # failures will have a 'task_errors' key, but not a 'task_result' key.

print(f'{actual_result=}')
```

# Changelog
1.0.0 - 1.0.3: Initial submissions

1.0.4: Fix #3: Don't use Walrus operator in code targeting python version 3.7.