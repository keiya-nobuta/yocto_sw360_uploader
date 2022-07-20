# (c) Keiya Nobuta <nobuta.keiya@fujitsu.com>
# SPDX-License-Identifier: MIT

import os
import json

class yocto_spdx_namespace:
    # RefDocs
    namespace = {}
    generated_ref = {}
    builddep_ref = {}

    def __init__(self, deploy_path='tmp/deploy', machine=[]):
        self._deploy_path = deploy_path
        self._spdx_dir = os.path.join(self._deploy_path, 'spdx')
        self._machine = list(machine) if machine else os.listdir(self._spdx_dir)
        self._by_namespace = [os.path.join(self._spdx_dir, m, 'by-namespace') for m in self._machine]
        self._packages = [os.path.join(self._spdx_dir, m, 'packages') for m in self._machine]
        self._recipes = [os.path.join(self._spdx_dir, m, 'recipes') for m in self._machine]

        for packages in self._packages:
            if not os.path.isdir(packages):
                raise NameError

    def import_single_spdx(self, filename):
        with open(filename, 'r') as f:
            spdxj = json.load(f)

        ns = spdxj['documentNamespace']
        self.namespace[ns] = spdxj

        return spdxj

    def import_single_spdx_with_refs(self, filename):
        spdx = self.import_single_spdx(filename)
        if 'externalDocumentRefs' not in spdx:
            return

        ns = spdx['documentNamespace']
        refdocs = dict([(ref['externalDocumentId'], ref['spdxDocument'])
                                for ref in spdx['externalDocumentRefs']])

        for rel in spdx['relationships']:
            rel_type = rel['relationshipType']
            if rel_type not in ('GENERATED_FROM', 'BUILD_DEPENDENCY_OF'):
                continue

            if rel_type == 'GENERATED_FROM':
                elm = rel['relatedSpdxElement']
                try:
                    refid, reftype = elm.split(':')
                except ValueError:
                    # 'NOASSERTION'
                    continue

            elif rel_type == 'BUILD_DEPENDENCY_OF':
                elm = rel['spdxElementId']
                try:
                    refid, reftype = rel['spdxElementId'].split(':')
                except ValueError:
                    # 'NOASSERTION'?
                    continue
            else:
                continue

            if not reftype.startswith("SPDXRef-"):
                continue

            ref_name = refdocs[refid]
            if ref_name not in self.namespace:
                for byn in self._by_namespace:
                    refname = os.path.join(byn, ref_name.replace('/', '_'))
                    if not os.path.islink(refname):
                        continue

                    ref_spdx = self.import_single_spdx_with_refs(refname)

            if rel_type == 'GENERATED_FROM':
                self.generated_ref[ns] = ref_name

            if rel_type == 'BUILD_DEPENDENCY_OF':
                if ns not in self.builddep_ref:
                    self.builddep_ref[ns] = [ref_name]
                else:
                    self.builddep_ref[ns].append(ref_name)

        return spdx

    def _find_spdx_name(self, name, dirs):
        for _dir in dirs:
            spdx_path = os.path.join(_dir, name + '.spdx.json')
            if os.path.isfile(spdx_path):
                return spdx_path

        return None

    def find_spdx_in_packages(self, pkg_name):
        return self._find_spdx_name(pkg_name, self._packages)

    def find_spdx_in_recipes(self, recipe_name):
        return self._find_spdx_name(recipe_name, self._recipes)

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Invalid args", file=sys.stderr)
        sys.exit(1)

    deploy_path = os.environ.get('DEPLOY_PATH', 'tmp/deploy')
    machine = os.environ.get('MACHINE')

    ns = yocto_spdx_namespace(deploy_path, machine)

    ns.import_single_spdx_with_refs(sys.argv[1])
    print(ns.namespace)

