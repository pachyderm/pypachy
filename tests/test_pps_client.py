#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for the `PpsClient` class of the `python_pachyderm` package."""

import time
import pytest

import python_pachyderm


@pytest.fixture(scope='function')
def pps_client():
    """Connect to Pachyderm before tests and reset to initial state after tests."""
    client = python_pachyderm.PpsClient()
    client.delete_all()
    yield client 
    client.delete_all()


@pytest.fixture(scope='function')
def pps_client_with_sandbox():
    """Connect to Pachyderm before tests and reset to initial state after tests."""

    pfs_client = python_pachyderm.PfsClient()
    pps_client = python_pachyderm.PpsClient()

    pps_client.delete_all()
    pfs_client.delete_all()

    pfs_client.create_repo('test-pps-input', 'This is a test repository for PPS functionality')

    pps_client.create_pipeline(
        "test-pps-copy",
        transform=python_pachyderm.Transform(cmd=["sh"], image="alpine", stdin=["cp /pfs/test-pps-input/*.dat /pfs/out/"]),
        input=python_pachyderm.Input(pfs=python_pachyderm.PFSInput(glob="/*", repo="test-pps-input")),
    )

    yield pps_client, pfs_client

    pps_client.delete_all()
    pfs_client.delete_all()

def wait_for_job(pps_client, sleep=0.01):
    for i in range(1000):
        jobs = pps_client.list_job()

        if len(jobs.job_info) > 0:
            return jobs.job_info[0].job.id

        if sleep is not None:
            time.sleep(sleep)

    assert False, "failed to wait for job"

def test_list_job(pps_client_with_sandbox):
    pps_client, pfs_client = pps_client_with_sandbox

    jobs = pps_client.list_job()
    assert len(jobs.job_info) == 0

    with pfs_client.commit('test-pps-input', 'master') as c:
        pfs_client.put_file_bytes(c, 'file.dat', b'DATA')

    job_id = wait_for_job(pps_client)

    jobs = pps_client.list_job()
    assert len(jobs.job_info) == 1

    jobs = pps_client.list_job(pipeline_name='test-pps-copy')
    assert len(jobs.job_info) == 1

    jobs = pps_client.list_job(input_commit=f"test-pps-input/{c.id}")
    assert len(jobs.job_info) == 1

def test_inspect_job(pps_client_with_sandbox):
    pps_client, pfs_client = pps_client_with_sandbox

    with pfs_client.commit('test-pps-input', 'master') as c:
        pfs_client.put_file_bytes(c, 'file.dat', b'DATA')

    job_id = wait_for_job(pps_client)
    job = pps_client.inspect_job(job_id)
    assert job.job.id == job_id

def test_stop_job(pps_client_with_sandbox):
    pps_client, pfs_client = pps_client_with_sandbox

    with pfs_client.commit('test-pps-input', 'master') as c:
        pfs_client.put_file_bytes(c, 'file.dat', b'DATA')

    job_id = wait_for_job(pps_client, sleep=None)

    # This may fail if the job finished between the last call and here. It's
    # not ideal, but the alternative would be to just ensure that this throws
    # an exception when called after the job has succeeded.
    pps_client.stop_job(job_id)

    # This is necessary because `StopJob` does not wait for the job to be
    # killed before returning a result.
    # TODO: remove once this is fixed:
    # https://github.com/pachyderm/pachyderm/issues/3856
    time.sleep(1) 

    job = pps_client.inspect_job(job_id)
    assert job.state == python_pachyderm.JOB_KILLED

def test_delete_job(pps_client_with_sandbox):
    pps_client, pfs_client = pps_client_with_sandbox

    with pfs_client.commit('test-pps-input', 'master') as c:
        pfs_client.put_file_bytes(c, 'file.dat', b'DATA')

    job_id = wait_for_job(pps_client)
    pps_client.delete_job(job_id)
    jobs = pps_client.list_job()
    assert len(jobs.job_info) == 0
