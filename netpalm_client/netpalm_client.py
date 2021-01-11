import json
import logging
import time
from typing import Dict, List

import requests

from .utils import netpalm_status, redis_status

log = logging.getLogger(__name__)


class NetpalmError(Exception):
    pass


class NetpalmConnectionError(NetpalmError):
    pass


class NetpalmStatusFail(NetpalmError):
    pass


class NetpalmNoData(NetpalmError):
    pass


class NetpalmTimeout(NetpalmError):
    pass


class APIClientBase:
    def _new_session(self):
        raise NotImplementedError

    url: str = None

    _session: requests.Session = None

    def get(self, endpoint: str, params: Dict = None, raise_for_status=False) -> Dict:
        """Returns ['data'] from result, raises appropriate errors
        :param endpoint:
        :param params: url parameters
        :param raise_for_status: whether to raise NetpalmStatusFail when netpalm status is valid, but indicates failure
        """
        return self._req(method='GET', endpoint=endpoint, params=params, raise_for_status=raise_for_status)

    def post(self, endpoint: str, params: Dict = None,
             body: Dict = None, raise_for_status=False) -> Dict:
        """Returns ['data'] from result, raises appropriate errors
        :param endpoint:
        :param params: url parameters
        :param body: data to be JSON encoded as body of POST
        :param raise_for_status: whether to raise NetpalmStatusFail when netpalm status is valid, but indicates failure
        """
        return self._req(method='POST', endpoint=endpoint, params=params, body=body, raise_for_status=raise_for_status)

    def delete(self, endpoint: str, params: Dict = None,
               body: Dict = None, raise_for_status=False) -> Dict:
        return self._req(method='DELETE', endpoint=endpoint, params=params, body=body,
                         raise_for_status=raise_for_status)

    def _req(self, method: str, endpoint: str, raise_for_status: bool,
             params: Dict = None, body: Dict = None, ):
        if params is None:
            params = {}

        if body is None:
            body = {}

        url = f'{self.url}/{endpoint}'

        kwargs = {
            'url': url,
            'params': params
        }

        try:
            if method == 'GET':
                raw_response = self._session.get(**kwargs)
            elif method == 'POST':
                kwargs.update({
                    'json': body
                })
                raw_response = self._session.post(**kwargs)
            elif method == 'DELETE':
                kwargs.update({
                    'json': body
                })
                raw_response = self._session.delete(**kwargs)
            else:
                raise NotImplementedError(f'HTTP method {method} not implemented in {self.__class__.__name__}._req()')
        except requests.exceptions.BaseHTTPError as err:
            raise NetpalmConnectionError() from err

        try:
            raw_response.raise_for_status()
        except requests.exceptions.BaseHTTPError as err:
            msg = f'Got error {err} using {method}ing to {endpoint} with {params=} and {body=}'
            raise NetpalmConnectionError(msg) from err

        try:
            result = raw_response.json()
            if type(result) is not dict:
                result = {
                    'data': result
                }
        except json.JSONDecodeError:
            if raw_response.status_code == 204:
                return

            raise NetpalmError(f'could not decode json from netpalm response: '
                               f'{raw_response} with content: {raw_response.content}'
                               f'from {method}ing to {endpoint} with {params=} and {body=}')

        status = result.get('status')

        data = result.get('data')

        if raise_for_status:
            if status not in netpalm_status:
                raise NetpalmStatusFail(f'Got invalid status {status} for {endpoint}')
            if status not in netpalm_status.ok_status:
                raise NetpalmStatusFail(f'Got failed {status=} for {endpoint}')

            if not data:
                raise NetpalmNoData(f'Got no data in response: {result} for endpoint: {endpoint}')

        if not data:
            data = result

        return data

    def __repr__(self):
        return f'{self.__class__.__name__}(url={self.url})'


class NetpalmClient(APIClientBase):
    def __init__(self, url: str, key: str, cli_user: str = None, cli_pass: str = None,
                 cache: bool = True, cache_ttl: int = 300):
        self.url = url
        self.key = key
        self.cli_user = cli_user
        self.cli_pass = cli_pass
        self.default_queue_strategy = 'pinned'
        self.cache = cache
        self.cache_ttl = cache_ttl

        self._new_session()

    def _new_session(self):
        log.info(f'Creating new Netpalm session to {self.url}, caching {"enabled" if self.cache else "disabled"}.')
        if self.cache:
            log.info(f'cache TTL set to {self.cache_ttl}s')
        self._session = requests.Session()
        self._session.headers = {
            'x-api-key': self.key
        }

    def check_task(self, task_id):
        """Check the status of a task, raise NetpalmStatusFail for invalid status'."""
        endpoint = f'task/{task_id}'
        rslt = self.get(endpoint, raise_for_status=True)
        if (task_status := rslt.get('task_status')) not in redis_status:
            raise NetpalmStatusFail(f'Task Status {task_status} from {endpoint} is not valid!')

        return rslt

    def poll_task(self, task_id: str, interval: int = 1, timeout: int = 30) -> Dict:
        start_time = time.time()

        while True:
            run_time = time.time() - start_time
            if run_time >= timeout:
                raise NetpalmTimeout(f'Timeout {timeout} seconds exceeded waiting for {task_id=}')

            result = self.check_task(task_id)
            status = result['task_status']
            log.debug(f'got {status=} for {task_id=}')
            if status in redis_status.done_status:
                break

            time.sleep(interval)

        return result

    def poll_tasks(self, task_ids: List[str], interval: int = 1, label='') -> Dict:
        """
        :param label:
        :param task_ids:
        :param interval:
        :return:  {
            task_id: result
        }
        """
        results = {}
        task_ids = set(task_ids)
        finished_task_ids = set()

        unfinished_task_ids = task_ids.difference(finished_task_ids)
        while True:
            for task_id in unfinished_task_ids.copy():
                try:
                    result = self.check_task(task_id)

                except NetpalmTimeout:
                    status = redis_status.FAILED
                    result = {'error': 'NetpalmTimeout'}

                else:
                    status = result['task_status']

                log.debug(f'got {status=} for {task_id=}')
                if status in redis_status.done_status:
                    results[task_id] = result
                    finished_task_ids.add(task_id)

            unfinished_task_ids = task_ids.difference(finished_task_ids)
            if not unfinished_task_ids:
                break

            log.info(f'{label} {len(unfinished_task_ids)} unfinished tasks out of {len(task_ids)}')
            time.sleep(interval)

        return results

    @property
    def task_queue(self):
        return self.get('taskqueue')['task_id']

    def raw_getconfig(self, library: str, command: str,
                      connection_args: Dict, library_args: Dict,
                      queue_strategy: str, poison: bool = False) -> Dict:
        body = {
            'library': library,
            'connection_args': connection_args,
            'args': library_args,
            'command': command,
            'queue_strategy': queue_strategy,
        }

        cache_config = {
            'enabled': True,
            'ttl': self.cache_ttl,
            'poison': poison
        }

        if self.cache:
            body['cache'] = cache_config

        return self.post('getconfig', body=body)

    def netmiko_getconfig(self, command: str, host: str, device_type: str, use_textfsm=True, textfsm_template=None,
                          timeout=5, queue_strategy: str = None, poison: bool = False) -> Dict:
        if queue_strategy is None:
            queue_strategy = self.default_queue_strategy

        connection_args = {
            'device_type': device_type,
            'host': host,
            'username': self.cli_user,
            'password': self.cli_pass,
            'timeout': timeout,
            'conn_timeout': timeout,
        }

        library_args = {
            'use_textfsm': use_textfsm,
            'textfsm_template': textfsm_template
        }

        return self.raw_getconfig(library='netmiko', command=command, connection_args=connection_args,
                                  library_args=library_args, queue_strategy=queue_strategy, poison=poison)
