# coding=utf-8

""" Batch module """

import ee
from . import alerts, utils
import requests
import os
import math


def downloadFile(url, name, ext, path=None):
    """ Download a file from a given url

    :param url: full url
    :type url: str
    :param name: name for the file (can contain a path)
    :type name: str
    :param ext: extension for the file
    :type ext: str
    :return: the created file (closed)
    :rtype: file
    """
    response = requests.get(url, stream=True)
    code = response.status_code

    if path is None:
        path = os.getcwd()

    path = os.path.join(path, name)

    while code != 200:
        if code == 400:
            return None
        response = requests.get(url, stream=True)
        code = response.status_code
        size = response.headers.get('content-length', 0)
        if size: print('size:', size)

    filename = '{}.{}'.format(path, ext)

    with open(filename, "wb") as handle:
        for data in response.iter_content():
            handle.write(data)

    return handle


def _download(image, region, name, limit=100, total_download=300,
              extension='json', path=None):
    vector = utils.make_vector(image, region)
    iterations = math.ceil(total_download/limit)

    for i in range(iterations):
        i += 1
        vlist = vector.toList(limit, limit*i)
        v = ee.FeatureCollection(vlist)

        name_i = '{}_{}'.format(name, i)
        url = v.getDownloadURL(**{
                'filetype': extension,
                'filename': name_i
              })
        downloadFile(url, name_i, extension, path)


def download_probable(site, date, limit=1, smooth='max', property_name=None,
                      path=None, extension='json', features_per_file=100,
                      total_features=300):
    """ Download probable alert vector. Parameter `site` can be a
    FeatureCollection in which case will be splitted with `property_name`
    parameter
    """
    if isinstance(site, ee.FeatureCollection):
        geom = site.geometry()
    else:
        geom = site

    alert = alerts.get_probable(geom, date, limit, smooth)

    count = utils.histogram(alert, 'probable', geom)

    # Make a request to handle empty alerts
    count_client = count.getInfo()

    if count_client > 0:
        if isinstance(site, ee.FeatureCollection) and property_name:
            names = utils.get_options(site, property_name)
            names_cli = names.getInfo()
            for name in names_cli:
                region = site.filterMetadata(
                    property_name, 'equals', name).first().geometry()
                filename = 'probable_alert_for_{}_{}'.format(date, name)
                _download(alert, region, filename, features_per_file,
                          total_features, extension, path)
        else:
            filename = 'probable_alert_for_{}'.format(date)
            _download(alert, geom, filename, features_per_file,
                      total_features, extension, path)
