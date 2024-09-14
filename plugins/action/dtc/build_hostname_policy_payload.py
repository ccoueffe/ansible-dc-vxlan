# Copyright (c) 2024 Cisco Systems, Inc. and its affiliates
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# SPDX-License-Identifier: MIT

from __future__ import absolute_import, division, print_function


__metaclass__ = type

import requests
from ansible.utils.display import Display
from ansible.plugins.action import ActionBase

display = Display()


class ActionModule(ActionBase):

    def run(self, tmp=None, task_vars=None):
        results = super(ActionModule, self).run(tmp, task_vars)

        switch_list = self._task.args['model_data']
        domain = self._task.args['domain']
        userName = self._task.args['userName']
        userPasswd = self._task.args['userPasswd']
        nd = self._task.args['nd']

        policy_payload = []
        policy_match = []

        URL = 'https://'+ nd +'/login'
        PAYLOAD = {
        "userName": userName,
        "userPasswd": userPasswd,
        "domain": domain
        }

        response = requests.post(url=URL, json=PAYLOAD, verify=False, timeout=30)
        resp = response.json()
        token = resp['jwttoken']

        # Get ND Policies for each switches
        PAYLOAD = ""
        headers = {'Cookie': "AuthCookie="+token+""}

        for switch in switch_list:
            # Get Intent SN and Hostname
            source_sn = switch["serial_number"]
            source_hostname = switch["name"]

            URL = ("https://"+
                nd+
                "/appcenter/cisco/ndfc/api/v1/lan-fabric/rest/control/policies/switches/"+
                source_sn+
                "/SWITCH/SWITCH")
            try:
                response = requests.request("GET", url=URL, headers=headers, data=PAYLOAD,
                                            verify=False, timeout=60)
                resp = response.json()
                for i in resp:
                    # Search Policy where templateName equal to host_11_1
                    if i['templateName'] == "host_11_1":
                        # If hostname is not equal, then update policy
                        if source_hostname != i['nvPairs']['SWITCH_NAME']:
                            policy_match = i
                            policy_match["nvPairs"]["SWITCH_NAME"] = switch["name"]
                            policy_payload.append(policy_match)

            except requests.exceptions.Timeout:
                response = requests.request("GET", url=URL, headers=headers, data=PAYLOAD,
                                            verify=False, timeout=60)
                resp = response.json()
                for i in resp:
                    # Search Policy where templateName equal to host_11_1
                    if i['templateName'] == "host_11_1":
                        # If hostname is not equal, then update policy
                        if source_hostname != i['nvPairs']['SWITCH_NAME']:
                            policy_match = i
                            policy_match["nvPairs"]["SWITCH_NAME"] = switch["name"]
                            policy_payload.append(policy_match)

        results['policy_payload'] = policy_payload
        results['policy_ids'] = "%2C".join([str(policy["id"]) for policy in policy_payload])

        return results