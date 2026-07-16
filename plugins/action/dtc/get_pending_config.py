# Copyright (c) 2025-2026 Cisco Systems, Inc. and its affiliates
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

import os
from time import monotonic

from ansible.utils.display import Display
from ansible.plugins.action import ActionBase

display = Display()

MAX_DISPLAY_LINES = 50


class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        results = super(ActionModule, self).run(tmp, task_vars)
        task_vars = task_vars or {}

        fabric_name = self._task.args.get("fabric_name")
        switches = self._task.args.get("switches", [])
        output_dir = self._task.args.get("output_dir", "")

        if not fabric_name:
            return {"failed": True, "msg": "fabric_name is required"}

        if not switches:
            return {"failed": True, "msg": "switches is required"}

        base_path = "/appcenter/cisco/ndfc/api/v1/lan-fabric/rest"

        # Extract serial numbers from data model
        serial_list = []
        for sw in switches:
            serial = sw.get("serial_number", "")
            name = sw.get("name", sw.get("hostname", "unknown"))
            if serial:
                serial_list.append({"serial": serial, "name": name})

        if not serial_list:
            display.display(
                f"PENDING CONFIG [{fabric_name}] no switches in data model",
                color="green",
            )
            return {"changed": False, "msg": "No switches in data model"}

        step_start = monotonic()
        display.display(
            f"\n{'─' * display.columns}\n"
            f"PENDING CONFIG [{fabric_name}] checking {len(serial_list)} switch(es)\n"
            f"{'─' * display.columns}",
            color="dark gray",
        )

        pending_count = 0
        for sw in serial_list:
            serial = sw["serial"]
            name = sw["name"]
            pending_path = (
                f"{base_path}/control/fabrics/{fabric_name}/pendingConfig/{serial}"
            )
            resp = self._send_request("GET", pending_path, task_vars, tmp)
            config_data = resp.get("DATA", resp)

            lines = self._extract_diff_lines(config_data)
            line_count = len(lines)

            if line_count == 0:
                display.v(f"  {name} ({serial}) — no pending config")
                continue

            pending_count += 1

            # Always show summary
            display.display(
                f"  {name} ({serial}) — {line_count} lines pending",
                color="yellow",
            )

            # Show diff only in verbose mode
            if display.verbosity >= 1:
                if line_count <= MAX_DISPLAY_LINES:
                    display.display(
                        f"\n  ┌─ {name} ({serial})",
                        color="cyan",
                    )
                    for line in lines:
                        display.display(f"  │ {line}", color="cyan")
                    display.display("  └─", color="cyan")
                else:
                    display.display(
                        f"\n  ┌─ {name} ({serial}) — showing first 10 lines",
                        color="cyan",
                    )
                    for line in lines[:10]:
                        display.display(f"  │ {line}", color="cyan")
                    display.display(
                        f"  │ ... ({line_count - 10} more lines)",
                        color="yellow",
                    )
                    display.display("  └─", color="yellow")

            # Save to file
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                filename = f"pending_config_{name}_{serial}.txt"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "w") as f:
                    f.write("\n".join(lines))
                display.v(f"  Saved pending config to {filepath}")

        elapsed = monotonic() - step_start
        if pending_count == 0:
            display.display(
                f"PENDING CONFIG [{fabric_name}] "
                f"no pending config on any switch [{elapsed:.1f}s]",
                color="green",
            )
        else:
            display.display(
                f"\nPENDING CONFIG [{fabric_name}] "
                f"{pending_count} switch(es) with pending config [{elapsed:.1f}s]",
                color="yellow",
            )

        return {
            "changed": False,
            "msg": f"{pending_count} switch(es) with pending config",
        }

    def _send_request(self, method, path, task_vars, tmp):
        module_args = {
            "method": method,
            "path": path,
        }
        response = self._execute_module(
            module_name="cisco.dcnm.dcnm_rest",
            module_args=module_args,
            task_vars=task_vars,
            tmp=tmp,
        )
        if isinstance(response, dict) and "response" in response:
            response = response["response"]
        if (
            isinstance(response, dict)
            and "msg" in response
            and isinstance(response["msg"], dict)
        ):
            response = response["msg"]
        if not isinstance(response, dict):
            response = {"DATA": response, "RETURN_CODE": -1}
        return response

    @staticmethod
    def _extract_diff_lines(config_data):
        if isinstance(config_data, str):
            return config_data.splitlines()
        if isinstance(config_data, list):
            lines = []
            for item in config_data:
                if isinstance(item, dict):
                    pending = item.get("pendingConfig", "")
                    if isinstance(pending, list):
                        for p in pending:
                            lines.extend(str(p).splitlines())
                    elif pending:
                        lines.extend(str(pending).splitlines())
                elif isinstance(item, str):
                    lines.extend(item.splitlines())
                else:
                    lines.extend(str(item).splitlines())
            return lines
        if isinstance(config_data, dict):
            pending = config_data.get("pendingConfig", "")
            if isinstance(pending, list):
                lines = []
                for p in pending:
                    lines.extend(str(p).splitlines())
                return lines
            if pending:
                return str(pending).splitlines()
        return []
