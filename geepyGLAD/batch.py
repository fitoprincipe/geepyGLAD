# coding=utf-8

""" Batch module """

import ee
from . import alerts, utils
import requests
import os
from geetools import batch as gbatch


FUNCTIONS = {
    'probable': alerts.get_probable,
    'confirmed': alerts.get_confirmed,
    'both': alerts.oneday,
    'period': alerts.period
}


def mask(image, vector, raster):
    """ Mask out a vector mask or a raster mask """
    if vector:
        return image.clip(vector)
    elif raster:
        return image.updateMask(raster)
    else:
        return image


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


def _download(vector, name, extension='JSON', path=None, verbose=True,
              logger=None):
    if extension in ['JSON', 'json', 'geojson', 'geoJSON']:
        try:
            gbatch.Download.table.toGeoJSON(vector, name, path)
        except Exception as e:
            msg = 'Download method failed: {} \n\ntrying another method...'.format(e)
            if verbose:
                print(msg)
            if logger:
                logger.log(msg)
            try:
                gbatch.Download.table.toLocal(vector, name, 'geojson',
                                              path=path)
            except Exception as e:
                msg = "Download failed: {}".format(e)
                if verbose:
                    print(msg)
                if logger:
                    logger.log(msg)
    else:
        print('Format {} not supported'.format(extension))


def _toDrive(vector, filename, folder, extension, **kwargs):
    verbose = kwargs.get('verbose', False)
    logger = kwargs.get('logger', None)

    try:
        task = ee.batch.Export.table.toDrive(vector, filename,
                                             folder, filename,
                                             extension)
        task.start()
        msg = 'uploading {} to {} in GDrive'.format(filename, folder)
        if verbose:
            print(msg)
        if logger:
            logger.log(msg)

    except Exception as e:
        msg = 'ERROR writing {} - {}'.format(filename, e)
        if verbose:
            print(msg)
        if logger:
            logger.log(msg)


def _toAsset(vector, filename, folder, **kwargs):
    verbose = kwargs.get('verbose', False)
    logger = kwargs.get('logger', None)

    user = ee.data.getAssetRoots()[0]['id']
    path = '{}/{}'.format(user, folder)

    assetId = '{}/{}'.format(path, filename)

    try:
        # task = ee.batch.Export.table.toAsset(vector, filename, assetId)
        # task.start()
        gbatch.Export.table.toAsset(vector, path, filename)
        msg = 'uploading {} to {} in Assets'.format(filename, path)
        if verbose:
            print(msg)
        if logger:
            logger.log(msg)

    except Exception as e:
        msg = 'ERROR in {} to {} in Assets - {}'.format(filename, path, e)
        if verbose:
            print(msg)
        if logger:
            logger.log(msg)


def _toLocal(vector, filename, folder=None, extension='geojson',
             subfolders=True, subname=None, **kwargs):

    verbose = kwargs.get('verbose', True)
    logger = kwargs.get('logger', None)

    # MANAGE ALERTS PATH
    if folder is None:
        folder = os.path.join(os.getcwd(), 'alerts')

    # make path if not present
    if not os.path.isdir(folder):
        if verbose:
            print('creating {} folder'.format(folder))
        os.mkdir(folder)

    if subfolders:
        subpath = os.path.join(folder, subname)
        if not os.path.isdir(subpath):
            if verbose:
                print('creating {}'.format(subpath))
            os.mkdir(subpath)
    else:
        subpath = folder

    msg = '{}: Downloading "{}" to "{}"'.format(subname, filename, subpath)
    if verbose:
        print(msg)
    if logger:
        logger.log(msg)

    try:
        _download(vector, filename, extension, subpath)
    except Exception as e:
        msg = '{}: ERROR writing {}'.format(subname, filename)
        if logger:
            logger.log(msg)
    else:
        msg = '{}: "{}" downloaded to "{}"'.format(subname, filename, subpath)
        if logger:
            logger.log(msg)


def _are_alerts(alert, name, date, clas, region, verbose, logger):
    try:
        count = utils.histogram(alert, clas, region).getInfo()
    except Exception as e:
        msg = '{}: ERROR getting histogram - {}'.format(name, e)
        if logger:
            logger.log(msg)
        return False

    if count == 0:
        msg = '{}: no alerts for {}'.format(name, date)
        if verbose:
            print(msg)
        if logger:
            logger.log(msg)
        return False
    else:
        return True


def _process_period(start, end, geometry, limit, year=None,
                    eightConnected=False, useProxy=False, mask=None,
                    destination='local', name=None, folder=None, **kwargs):
    verbose = kwargs.get('verbose', True)
    logger = kwargs.get('logger', None)

    try:
        alert = FUNCTIONS['period'](start, end, geometry, limit, year,
                                    eightConnected, useProxy, mask)
    except Exception as e:
        msg = 'ERROR while getting period alert {} to {}'.format(start, end)
        if verbose:
            print(msg)
        if logger:
            logger.log(msg)
        raise e

    date_str = '{} to {}'.format(start, end)

    are_alerts = _are_alerts(alert, name, date_str, 'both', geometry, **kwargs)
    if not are_alerts:
        return None
    
    filename = '{}_{}_to_{}'.format(name, start, end)

    vector = utils.make_alerts_vector(alert, geometry)
    # LOCAL
    if destination == 'local':
        subfolders = kwargs.get('subfolders', True)
        ext = kwargs.get('extension', 'geojson')
        _toLocal(vector, filename, folder, ext, subfolders,
                 name, **kwargs)

    elif destination == 'drive':
        filename = filename.encode().decode('ascii', errors='ignore')
        ext = kwargs.get('extension', 'geojson')
        _toDrive(vector, filename, folder, ext, **kwargs)

    elif destination == 'asset':
        _toAsset(vector, filename, folder, **kwargs)


def _process(geometry, date, clas, limit, folder, raster_mask, destination,
             filename,  name, **kwargs):
    verbose = kwargs.get('verbose', True)
    logger = kwargs.get('logger', None)

    try:
        alert = FUNCTIONS[clas](geometry, date, limit, mask=raster_mask)
    except Exception as e:
        msg = 'ERROR while getting alert for {}'.format(date)
        if verbose:
            print(msg)
        if logger:
            logger.log(msg)
        raise e

    # SKIP IF EMPTY ALERT
    are_alerts = _are_alerts(alert, name, date, clas, geometry, **kwargs)
    if not are_alerts:
        return None

    vector = utils.make_alerts_vector(alert, geometry)
    # LOCAL
    if destination == 'local':
        subfolders = kwargs.get('subfolders', True)
        ext = kwargs.get('extension', 'geojson')
        _toLocal(vector, filename, folder, ext, subfolders,
                 name, **kwargs)

    elif destination == 'drive':
        filename = filename.encode().decode('ascii', errors='ignore')
        ext = kwargs.get('extension', 'geojson')
        _toDrive(vector, filename, folder, ext, **kwargs)

    elif destination == 'asset':
        _toAsset(vector, filename, folder, **kwargs)


def period(site, start, end, limit, proxy=False, eightConnected=False,
           folder=None, property_name=None, raster_mask=None,
           destination='local', verbose=True, logger=None):
    """ General download function for a period """   

    args = dict(verbose=verbose, logger=logger)

    # START PROCESS
    # If it is a FeatureCollection and there is a property name
    if isinstance(site, ee.FeatureCollection) and property_name:
        names = utils.get_options(site, property_name)
        names_cli = names.getInfo()
        for name in names_cli:

            geom = site.filterMetadata(
                property_name, 'equals', name).first().geometry()

            _process_period(start, end, geom, limit, None, eightConnected,
                            proxy, raster_mask, destination, name, folder,
                            **args)
    else:
        if isinstance(site, ee.Feature) and property_name:
            name = ee.String(site.get(property_name)).getInfo()
        else:
            name = 'N/A'

        # GET GEOMETRY
        if isinstance(site, (ee.FeatureCollection, ee.Feature)):
            geom = site.geometry()
        else:
            geom = site

        _process_period(start, end, geom, limit, None, eightConnected,
                        proxy, raster_mask, destination, name, folder,
                        **args)


def download(site, date, clas, limit, folder=None, property_name=None,
             raster_mask=None, destination='local', verbose=True, logger=None):
    """ General download function """
    if not utils.has_image(date, alerts.ALERTS).getInfo():
        msg = 'GLAD alerts not available for date {}'.format(date)
        if logger:
            logger.log(msg)
        return None

    if clas not in ['probable', 'confirmed', 'both']:
        clas = 'both'

    # BASE NAME FOR OUTPUT FILE
    if clas == 'both':
        basename = 'alerts_for'
    else:
        basename = '{}_alerts_for'.format(clas)

    args = dict(verbose=verbose, logger=logger)

    # START PROCESS
    # If it is a FeatureCollection and there is a property name
    if isinstance(site, ee.FeatureCollection) and property_name:
        names = utils.get_options(site, property_name)
        names_cli = names.getInfo()
        for name in names_cli:
            filename = '{}_{}_{}'.format(basename, date, name)

            geom = site.filterMetadata(
                property_name, 'equals', name).first().geometry()

            _process(geom, date, clas, limit, folder, raster_mask, destination,
                     filename,  name, **args)
    else:
        if isinstance(site, ee.Feature) and property_name:
            name = ee.String(site.get(property_name)).getInfo()
            filename = '{}_{}_{}'.format(basename, date, name)
        else:
            name = 'N/A'
            filename = '{}_{}'.format(basename, date)

        # GET GEOMETRY
        if isinstance(site, (ee.FeatureCollection, ee.Feature)):
            geom = site.geometry()
        else:
            geom = site

        _process(geom, date, clas, limit, folder, raster_mask, destination,
                 filename,  name, **args)
