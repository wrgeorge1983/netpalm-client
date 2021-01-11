
class RedisStatus:
    QUEUED = 'queued'
    FINISHED = 'finished'
    FAILED = 'failed'
    STARTED = 'started'
    DEFERRED = 'deferred'
    SCHEDULED = 'scheduled'

    valid_status = [
        'queued',
        'finished',
        'failed',
        'started',
        'deferred',
        'scheduled'
    ]

    failed_status = [
        'failed'
    ]

    done_status = [
        'failed',
        'finished'
    ]

    ok_status = [
        'queued',
        'finished',
        'started',
        'deferred',
        'scheduled'
    ]

    def __contains__(self, item):
        return item in self.valid_status


redis_status = RedisStatus()


class NetpalmStatus:
    SUCCESS = 'success'

    valid_status = [
        'success',
        'error'
    ]

    failed_status = [
        'error'
    ]

    ok_status = [
        'success'
    ]

    def __contains__(self, item):
        return item in self.valid_status


netpalm_status = NetpalmStatus()