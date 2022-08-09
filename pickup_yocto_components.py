# (c) Keiya Nobuta <nobuta.keiya@fujitsu.com>
# SPDX-License-Identifier: MIT

import os
import glob
import yocto_spdx
import nvd_cpe_detector

def _parse_manifest(manifest):
    ret = []
    with open(manifest, 'r') as f:
        for line in f:
            ret.append(line.split())

    return ret

def _each_manifests(manifest):
    for m in _parse_manifest(manifest):
        yield m

def _find_pkg(pkg_name, pkg_type, pkg_dir):
    return glob.glob(os.path.join(pkg_dir, pkg_name + '-' + pkg_type + '-*'))

def _find_src_pkg(pkg_name, pkg_dir):
    return _find_pkg(pkg_name, "src", pkg_dir)

def _find_lic_pkg(pkg_name, pkg_dir):
    return _find_pkg(pkg_name, "lic", pkg_dir)

def pickup_yocto_components(deploy_path="tmp/deploy", machine="qemux86-64", image="core-image-minimal", package_type=None):
    """
        deploy_path: Set tmp/deploy path (default: tmp/deploy)
        machine: Set MACHINE in conf/local.conf (default: qemux86-64)
        image: Set image name you bitbaked (default: core-image-minimal)
        package_type: Set "rpm", "ipk" or "deb" (default: detect from <deploy_path>)

    Returns:
        yield {'name': str,
               'version': str,
               'path': str}
    """
    if not deploy_path or not machine or not image:
        raise ValueError

    # find manifest
    deploy_image = os.path.join(deploy_path, 'images', machine)
    image_prefix = os.path.join(deploy_image, '-'.join((image, machine)))
    manifest = image_prefix + '.manifest'

    # package path (rpm|ipk|deb)
    ### package type detection if not package_type specified
    if not package_type:
        for p in ['rpm', 'ipk', 'deb']:
            _path = os.path.join(deploy_path, p)
            if os.path.isdir(_path):
                package_type = p
                break
    package_path = os.path.join(deploy_path, package_type)

    if not os.path.isdir(package_path):
        raise NameError

    try:
        ns = yocto_spdx.yocto_spdx_namespace(deploy_path, [machine])
    except:
        ns = None

    # find packages from manifest
    for name, arch, ver in _each_manifests(manifest):
        package_name = name + '-' + ver + '*.' + arch + '.' + package_type
        pkg_dir = os.path.join(package_path, arch)
        package = os.path.join(pkg_dir, package_name)
        package = glob.glob(package)[0]

        ret = {'name': name, 'version': ver, 'arch': arch, 'path': package}

        if not name.endswith('-src'):
            src_pkg = _find_src_pkg(name, pkg_dir)
            if src_pkg:
                ret['src_path'] = src_pkg[0]

        if not name.endswith('-lic'):
            lic_pkg = _find_lic_pkg(name, pkg_dir)
            if lic_pkg:
                ret['license_path'] = lic_pkg[0]

        if ns:
            spdx_path = ns.find_spdx_in_packages(name)
            if spdx_path:
                spdx = ns.import_single_spdx_with_refs(spdx_path)
                if spdx:
                    pkginfo = spdx['packages'][0]
                    ret['license'] = pkginfo['licenseDeclared']

                    pkg_ns = spdx['documentNamespace']
                    if pkg_ns in ns.generated_ref:
                        ref_spdx = ns.namespace[ns.generated_ref[pkg_ns]]
                        ref_pkginfo = ref_spdx['packages'][0]
                        ret['recipe'] = ref_pkginfo['name']
                        if 'description' in ref_pkginfo:
                            ret['description'] = ref_pkginfo['description']
                        if 'homepage' in ref_pkginfo:
                            ret['homepage'] = ref_pkginfo['homepage']
                        if 'downloadLocation' in ref_pkginfo and ref_pkginfo['downloadLocation'] != 'NOASSERTION':
                            ret['downloadURL'] = ref_pkginfo['downloadLocation']
                        if 'externalRefs' in ref_pkginfo and ref_pkginfo['externalRefs'][0]['referenceCategory'] == 'SECURITY':
                            cpe = ref_pkginfo['externalRefs'][0]['referenceLocator']
                            try:
                                cpe = nvd_cpe_detector.replace_vendor(cpe, ret['homepage'], ret['downloadURL'])
                            except:
                                pass
                            ret['CPE-ID'] = cpe
                        ret['recipeLicense'] = ref_pkginfo['licenseDeclared']

        yield ret

if __name__ == "__main__":
    """ test """
    deploy_path =  os.environ.get('DEPLOY_PATH')
    machine =      os.environ.get('MACHINE')
    image =        os.environ.get('IMAGE')

    for component in pickup_yocto_components(deploy_path, machine, image, package_type='rpm'):
        print(component)
