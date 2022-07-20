# (c) Keiya Nobuta <nobuta.keiya@fujitsu.com>
# SPDX-License-Identifier: MIT

import sw360
import os
import sys
import urllib.parse
import pickup_yocto_components as pyc
import fossology_trigger_daemon as fossd
import datetime


_name_conversion_table = {
        'kernel': 'linux',
}

def _convert_component_name(name):
    for k in _name_conversion_table:
        if name.startswith(k):
            return name.replace(k, _name_conversion_table[k])

    return name

def _parse_id(url):
    return urllib.parse.urlsplit(url).path.split('/')[-1]

def _create_project(sw360_client, project_name, project_ver):
    resp = sw360_client.get_projects_by_name(project_name)

    if not resp:
        project = sw360_client.create_new_project(name=project_name,
                                                  version=project_ver)
        if not project:
            return None
    else:
        resp = [p for p in resp if p['version'] == project_ver]
        if not resp:
            project = sw360_client.create_new_project(name=project_name,
                                                      version=project_ver)
            if not project:
                return None
        else:
            project = resp[0]

    project_url = project['_links']['self']['href']
    return _parse_id(project_url)

def _create_component(sw360_client, component_name, description='',
                      component_type='OSS', homepage=''):
    resp = sw360_client.get_component_by_name(component_name)
    releases = []

    component_url = None

    if resp and '_embedded' in resp and 'sw360:components' in resp['_embedded']:
        components = resp['_embedded']['sw360:components']
        for _component in components:
            if _component['name'] != component_name:
                continue

            component_url = _component['_links']['self']['href']

            resp = sw360_client.get_component_by_url(component_url)
            if not resp:
                return None

            if description and resp['description'] == description:
                break
            if homepage and resp['homepage'] == homepage:
                break
            if not resp['description'] and not resp['homepage']:
                break

        if '_embedded' in resp and 'sw360:releases' in resp['_embedded']:
            releases = resp['_embedded']['sw360:releases']

    if not component_url:
        resp = sw360_client.create_new_component(component_name, description,
                                                 component_type, homepage)
        if not resp:
            return None

        component_url = resp['_links']['self']['href']

    return _parse_id(component_url), releases

def _find_release_version(releases, version):
    for r in releases:
        if r['version'] == version:
            return r
    return None

def _add_release(sw360_client, component_id, component_name, version,
                 cpe_id='', downloadURL='', license='', release=None):
    if not release:
        release = sw360_client.create_new_release(name, version, component_id)
        if not release:
            return None

    release_id = _parse_id(release['_links']['self']['href'])

    # update
    update_release = release.copy()
    update_release['releaseDate'] = datetime.datetime.today().strftime('%Y-%m-%d')
    update_release['operatingSystems'] = ['Linux',]
    if cpe_id:
        update_release['cpeId'] = cpe_id
    if downloadURL:
        update_release['sourceCodeDownloadurl'] = dwonloadURL
               #'createdBy': , # for example `git config user.email`
               #'cpeId':,
               #'clearingState': 'NEW_CLEARING',
               #'mainlineState':, # 'OPEN', 'MAINLINE', 'SPECIFIC', 'PHASEOUT', 'DENIED'
               #'sourceCodeDownloadurl':,
               #'binaryDownloadurl':,
               #'externalIds':,
               #'additionalData':,
               #'languages': [],
               #'_embedded': {'sw360:licenses': []}}
    resp = sw360_client.update_release(update_release, release_id)
    if not resp:
        return None

    return release_id

def _upload_attachment(sw360_client, release_id, attach_path, attach_type):
    attach_name = os.path.basename(attach_path)
    resp = sw360_client.get_attachment_infos_for_release(release_id)
    if resp:
        for attach in resp:
            if attach['filename'] == attach_name:
                return None

    resp = sw360_client.upload_release_attachment(release_id, attach_path,
                                                  upload_type=attach_type)
    return resp

if __name__ == "__main__":
    sw360_url =    os.environ['SW360_URL']
    sw360_secret = os.environ['SW360_SECRET']
    project_name = os.environ['PROJECT_NAME']
    project_ver =  os.environ.get('PROJECT_VERSION', 'devel')
    deploy_path =  os.environ.get('DEPLOY_PATH')
    machine =      os.environ.get('MACHINE')
    image =        os.environ.get('IMAGE')


    sw360_client = sw360.SW360(url=sw360_url, token=sw360_secret)
    sw360_client.login_api()

    release_ids = set()
    fossology_target = set()
    for component in pyc.pickup_yocto_components(deploy_path, machine, image):
        name = component['name']
        version = component['version']
        attachment = component['path']
        component_name = _convert_component_name(name)
        src = component.get('src_path')

        resp = _create_component(sw360_client, component_name,
                                 description = component.get('description'),
                                 homepage = component.get('homepage'))
        if not resp:
            raise ValueError

        component_id, releases = resp
        release = _find_release_version(releases, version)

        release_id = _add_release(sw360_client, component_id, component_name, version,
                                  cpe_id = component.get('CPE-ID'),
                                  downloadURL = component.get('downloadLocation'),
                                  license = component.get('license'),
                                  release=release)
        if not release_id:
            raise ValueError

        if name.endswith('-src'):
            src = attachment

        if src:
            _upload_attachment(sw360_client, release_id, src, 'SOURCE')
            fossology_target.add(release_id)

        release_ids.add(release_id)

    project_id = _create_project(sw360_client, project_name, project_ver)
    if not project_id:
        raise ValueError

    sw360_client.update_project_releases(list(release_ids), project_id, add=True)

    fossd.fossology_trigger_daemon(sw360_client, list(fossology_target))
    sw360_client.close_api()
    print("Done")
