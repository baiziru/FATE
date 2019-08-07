#
#  Copyright 2019 The FATE Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import json

import grpc
import requests
from flask import jsonify

from fate_flow.settings import DEFAULT_GRPC_OVERALL_TIMEOUT
from fate_flow.settings import stat_logger, SERVER_HOST_URL, HEADERS
from fate_flow.utils.grpc_utils import wrap_grpc_packet, get_proxy_data_channel
from fate_flow.entity.service_support_config import WorkMode


def get_json_result(retcode=0, retmsg='success', data=None, job_id=None, meta=None):
    return jsonify({"retcode": retcode, "retmsg": retmsg, "data": data, "jobId": job_id, "meta": meta})


def federated_api(job_id, method, url_without_host, src_party_id, dest_party_id, json_body, work_mode,
                  overall_timeout=DEFAULT_GRPC_OVERALL_TIMEOUT):
    if work_mode == WorkMode.STANDALONE:
        try:
            stat_logger.info('local api request: {} {}'.format(url_without_host, json_body))
            response = local_api(method=method, url_with_host=url_without_host, json_body=json_body)
            response_json_body = response.json()
            stat_logger.info('local api response: {} {}'.format(url_without_host, response_json_body))
            return response_json_body
        except Exception as e:
            stat_logger.exception(e)
            return {'retcode': 104, 'msg': 'local api request error: {}'.format(e)}
    elif work_mode == WorkMode.CLUSTER:
        _packet = wrap_grpc_packet(json_body, method, url_without_host, src_party_id, dest_party_id, job_id,
                                   overall_timeout=overall_timeout)
        try:
            channel, stub = get_proxy_data_channel()
            stat_logger.info("grpc api request: {}".format(_packet))
            _return = stub.unaryCall(_packet)
            stat_logger.info("grpc api response: {}".format(_return))
            channel.close()
            json_body = json.loads(_return.body.value)
            return json_body
        except grpc.RpcError as e:
            stat_logger.exception(e)
            return {'retcode': 101, 'msg': 'rpc request error: {}'.format(e)}
        except Exception as e:
            stat_logger.exception(e)
            return {'retcode': 102, 'msg': 'rpc request error: {}'.format(e)}
    else:
        return {'retcode': 103, 'msg': '{} work mode is not supported'.format(work_mode)}


def local_api(method, url_with_host, json_body):
    url = "{}{}".format(SERVER_HOST_URL, url_with_host)
    action = getattr(requests, method.lower(), None)
    resp = action(url=url, json=json_body, headers=HEADERS)
    return resp