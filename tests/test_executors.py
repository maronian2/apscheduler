from datetime import datetime
from threading import Event
from types import TracebackType
import time
from traceback import format_tb
import sys

import pytest

from apscheduler.events import (EVENT_JOB_ERROR, EVENT_JOB_MISSED, EVENT_JOB_EXECUTED,
    JobExecutionEvent)
from apscheduler.executors.base import MaxInstancesReachedError
from apscheduler.schedulers.base import BaseScheduler

try:
    from unittest.mock import Mock, MagicMock
except ImportError:
    from mock import Mock, MagicMock


@pytest.fixture
def mock_scheduler(timezone):
    scheduler_ = Mock(BaseScheduler, timezone=timezone)
    scheduler_._create_lock = MagicMock()
    scheduler_._add_job_submission = MagicMock(return_value=1)
    return scheduler_


@pytest.yield_fixture(params=['threadpool', 'processpool'])
def executor(request, mock_scheduler):
    if request.param == 'threadpool':
        from apscheduler.executors.pool import ThreadPoolExecutor
        executor_ = ThreadPoolExecutor()
    else:
        from apscheduler.executors.pool import ProcessPoolExecutor
        executor_ = ProcessPoolExecutor()

    executor_.start(mock_scheduler, 'dummy')
    yield executor_
    executor_.shutdown()


def wait_event():
    time.sleep(0.2)
    return 'test'


def failure():
    raise Exception('test failure')


def success():
    return 5


def test_max_instances(mock_scheduler, executor, create_job, freeze_time):
    """Tests that the maximum instance limit on a job is respected."""
    events = []
    mock_scheduler._dispatch_event = lambda event: events.append(event)
    job = create_job(func=wait_event, max_instances=2, next_run_time=None)
    executor.submit_job(job, freeze_time.current)
    executor.submit_job(job, freeze_time.current)

    pytest.raises(MaxInstancesReachedError, executor.submit_job, job, freeze_time.current)
    executor.shutdown()
    assert len(events) == 2
    assert events[0].retval == 'test'
    assert events[1].retval == 'test'


@pytest.mark.parametrize('event_code,func', [
    (EVENT_JOB_EXECUTED, success),
    (EVENT_JOB_ERROR, failure)
], ids=['executed', 'error'])
def test_submit_job(mock_scheduler, executor, create_job, freeze_time, timezone, event_code, func):
    """
    Tests that an EVENT_JOB_EXECUTED event is delivered to the scheduler if the job was
    successfully executed.

    """

    mock_scheduler._dispatch_event = MagicMock()
    job = create_job(func=func, id='foo')
    job._jobstore_alias = 'test_jobstore'
    run_time = (timezone.localize(datetime(1970, 1, 1)) if event_code == EVENT_JOB_MISSED else
                freeze_time.current)
    executor.submit_job(job, run_time)
    executor.shutdown()

    assert mock_scheduler._dispatch_event.call_count == 1
    event = mock_scheduler._dispatch_event.call_args[0][0]
    assert event.code == event_code
    assert event.job_id == 'foo'
    assert event.jobstore == 'test_jobstore'

    if event_code == EVENT_JOB_EXECUTED:
        assert event.retval == 5
    elif event_code == EVENT_JOB_ERROR:
        assert str(event.exception) == 'test failure'
        assert isinstance(event.traceback, str)


class FauxJob(object):
    id = 'abc'
    max_instances = 1
    _jobstore_alias = 'foo'


def dummy_run_job(job, logger_name, job_submission_id, jobstore_alias, run_time):
    try:
        raise Exception("dummy")
    except:
        exc, tb = sys.exc_info()[1:]
        formatted_tb = ''.join(format_tb(tb))
        return JobExecutionEvent(EVENT_JOB_ERROR, job.id, jobstore_alias, run_time,
                             exception=exc, traceback=formatted_tb)


def test_run_job_error(monkeypatch, executor):
    """Tests that _run_job_error is properly called if an exception is raised in run_job()"""
    
    def run_job_error(_event):
        assert _event.job_id == 'abc'
        event_exception[:] = [_event.exception]
        event.set()

    event = Event()
    event_exception = [None]
    monkeypatch.setattr('apscheduler.executors.base.run_job', dummy_run_job)
    monkeypatch.setattr('apscheduler.executors.pool.run_job', dummy_run_job)
    monkeypatch.setattr(executor, '_run_job_error', run_job_error)
    executor.submit_job(FauxJob(), [])

    event.wait(2)
    assert str(event_exception[0]) == "dummy"



