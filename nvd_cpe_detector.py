
_nvd_cpe_api_url = 'https://services.nvd.nist.gov/rest/json/cpes/1.0'

def _get_match_cpe(cpe):
    import requests

    url = _nvd_cpe_api_url + '?' + cpe
    r = requests.get(url)

    if r and r.status_code == 200:
        if 'result' in r.json():
            return r.json()

    return None

def _match_domain(url1, url2):
    url1 = url1[url1.find('://') + 3:]
    url1 = url1[:url1.find('/')]

    url2 = url2[url1.find('://') + 3:]
    url2 = url2[:url1.find('/')]

    return (url1 == url2)

def _detect_vendor(product, homepage='', downloadUrl=''):
    result = _get_match_cpe(f'cpe:2.3:a:*:{product}')
    for c in result['cpes']:
        for ref in c['refs']:
            if ref['type'] == 'Product' and _match_domain(homepage, ref['ref']) or \
               ref['type'] == 'Version' and _match_domain(downloadUrl, ref['ref']):
                   cpe = c['cpe23Uri'].split(':')
                   vendor = cpe[3]
                   return vendor

    return None

def replace_vendor(cpe, homepage='', downloadUrl=''):
    if not cpe.startswith('cpe:2.3:a:'):
        raise TypeError

    cpe = cpe.split(':')
    vendor = cpe[3]
    product = cpe[4]

    if vendor == "*":
        new_vendor = _detect_vendor(product, homepage, downloadUrl)
        if new_vendor:
            vendor = new_vendor

    new_cpe = f'cpe:2.3:a:{vendor}:{product}:' + ':'.join(cpe[5:])
    return new_cpe
