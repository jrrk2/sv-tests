#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 The SymbiFlow Authors.
#
# Use of this source code is governed by a ISC-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/ISC
#
# SPDX-License-Identifier: ISC

import os
import shlex

from BaseRunner import BaseRunner


class Verilator_synth(BaseRunner):
    """Verilator "synthesis" branch (github.com/jrrk2/verilator).

    The branch adds synthesis backends at the --json-only cut point. The
    elaboration mode synthesizes the design to a structural primitive netlist
    (--struct-only-output), the counterpart of the Yosys runner's
    hierarchy/proc/memory flow. Like Yosys, unsynthesizable tests are skipped.
    """
    def __init__(self):
        super().__init__(
            "verilator-synth", "verilator-synth",
            {"preprocessing", "parsing", "elaboration"})

        self.allowed_extensions.extend(['.vlt'])
        self.submodule = "third_party/tools/verilator-synth"
        self.url = f"https://github.com/jrrk2/verilator/tree/{self.get_commit()}"

    def get_mode(self, params):
        if int(params['unsynthesizable']):
            return None
        return super().get_mode(params)

    def prepare_run_cb(self, tmp_dir, params):
        mode = params['mode']
        scr = os.path.join(tmp_dir, 'scr.sh')
        netlist = 'netlist.v'

        args = []
        if mode == 'preprocessing':
            args += ['-P', '-E']
        elif mode == 'parsing':
            args += ['--lint-only']
        else:  # elaboration: synthesize to a structural netlist
            args += ['--struct-only-output', netlist]

        args += ['-Wno-fatal', '-Wno-UNOPTFLAT', '-Wno-BLKANDNBLK']
        args += ['-Wpedantic', '-Wno-context']

        if params['top_module'] != '':
            args += ['--top-module', params['top_module']]

        for incdir in params['incdirs']:
            args.append('-I' + incdir)

        # Same front end as stock Verilator, so honour its per-test flags
        # (e.g. -Werror-WIDTH on should_fail tests) as well as our own.
        for key in ('runner_verilator_flags', 'runner_verilator_synth_flags'):
            if key in params:
                args += shlex.split(params[key])

        for define in params['defines']:
            args.append('-D' + define)

        args += params['files']

        with open(scr, 'w') as f:
            f.write('set -x\n')
            f.write(
                f'{self.executable} {" ".join(map(shlex.quote, args))}'
                ' || exit $?\n')
            if mode == 'elaboration':
                # a synthesis run must actually produce a netlist
                f.write(
                    f'test -s {netlist} || '
                    f'{{ echo "no netlist emitted" >&2; exit 1; }}\n')
                f.write(f'grep -c "^module" {netlist}\n')
                # logic the backend could not build is recorded only as
                # netlist comments; surface it in the log
                f.write(f'grep "// WARNING:" {netlist} || true\n')
                # Logic replaced by 0 or dropped is a wrong netlist, not a
                # pass.  Dropped initial/final blocks, $display and similar
                # testbench statements are expected of synthesis.
                lossy = '// WARNING: (unsupported|unsynthesizable|force/release)'
                f.write(
                    f"if grep -qE '{lossy}' {netlist}; then "
                    'echo "netlist is missing logic" >&2; exit 1; fi\n')

        self.cmd = ['sh', 'scr.sh']

    def get_version(self):
        version = super().get_version()
        # "Verilator 5.050 2026-07-01 rev v5.050-..." -> "verilator-synth 5.050"
        return " ".join([self.name, version.split()[1]])
