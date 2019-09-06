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
    'both': alerts.oneday
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


def _download(image, region, name, extension='JSON', path=None, verbose=True):

    # vector = utils.make_vector(image, region)
    vector = utils.make_alerts_vector(image, region)

    if extension in ['JSON', 'json', 'geojson', 'geoJSON']:
        try:
            gbatch.Download.table.toGeoJSON(vector, name, path)
        except Exception as e:
            if verbose:
                msg = 'Download method failed: \n {} \n, trying another method...'
                print(msg.format(e))
            gbatch.Download.table.toLocal(vector, name, 'JSON')
    else:
        print('Format {} not supported'.format(extension))


def toLocal(site, date, clas, limit=1, property_name=None,
            folder=None, extension='JSON', subfolders=True, verbose=True,
            vector_mask=None, raster_mask=None, logger=None):
    """ Download probable alert vector. Parameter `site` can be a
    FeatureCollection in which case will be splitted with `property_name`
    parameter
    """
    msgs = []

    if not utils.has_image(date, alerts.ALERTS).getInfo():
        msg = 'GLAD alerts not available for date {}'.format(date)
        if logger:
             logger.log(msg)
        return None

    extensions = {
        'JSON': 'geoJSON',
        'KML': 'kml',
        'CSV': 'csv'
    }

    if clas not in ['probable', 'confirmed', 'both']:
        clas = 'both'

    # BASE NAME FOR OUTPUT FILE
    if clas == 'both':
        basename = 'alerts_for'
    else:
        basename = '{}_alerts_for'.format(clas)

    # GET SITE
    if isinstance(site, (ee.FeatureCollection, ee.Feature)):
        geom = site.geometry()
    else:
        geom = site

    # MANAGE ALERTS PATH
    if folder is None:
        folder = os.path.join(os.getcwd(), 'alerts')

    # make path if not present
    if not os.path.isdir(folder):
        if verbose:
            print('creating {}'.format(folder))
        os.mkdir(folder)

    # START PROCESS
    # If it is a FeatureCollection and there is a property name
    if isinstance(site, ee.FeatureCollection) and property_name:
        names = utils.get_options(site, property_name)
        names_cli = names.getInfo()
        for name in names_cli:
            filename = '{}_{}_{}'.format(basename, date, name)

            region = site.filterMetadata(
                property_name, 'equals', name).first().geometry()

            alert = FUNCTIONS[clas](region, date, limit, mask=raster_mask)

            # SKIP IF EMPTY ALERT
            try:
                count = utils.histogram(alert, clas, region).getInfo()
            except Exception as e:
                msg = '{}: ERROR getting histogram - {}'.format(name, e)
                if logger:
                    logger.log(msg)
                continue

            if count == 0:
                msg = '{}: no alerts'.format(name)
                if verbose:
                    print(msg)
                if logger:
                    logger.log(msg)
                continue

            if subfolders:
                subpath = os.path.join(folder, name)
                if not os.path.isdir(subpath):
                    if verbose:
                        print('creating {}'.format(subpath))
                    os.mkdir(subpath)
            else:
                subpath = folder

            msg = '{}: Downloading "{}" to "{}"'.format(name, filename, subpath)
            if verbose:
                print(msg)
            if logger:
                logger.log(msg)

            try:
                _download(alert, region, filename, extension, subpath)
            except Exception as e:
                msg = '{}: ERROR writing {}'.format(name, filename)
                if logger:
                    logger.log(msg)
                continue
            else:
                msg = '{}: "{}" downloaded to "{}"'.format(name, filename, subpath)
                if logger:
                    logger.log(msg)
    # If NOT
    else:
        if isinstance(site, ee.Feature) and property_name:
            name = ee.String(site.get(property_name)).getInfo()
            filename = '{}_{}_{}'.format(basename, date, name)
        else:
            filename = '{}_{}'.format(basename, date)

        alert = FUNCTIONS[clas](geom, date, limit)

        # SKIP IF EMPTY ALERT
        try:
            count = utils.histogram(alert, clas, geom).getInfo()
        except Exception as e:
            msg = 'ERROR getting histogram - {}'.format(e)
            if logger:
                logger.log(msg)
            return None

        if count == 0:
            msg = '{} has no alerts'.format(filename)
            if verbose:
                print(msg)
            if logger:
                logger.log(msg)
            return None

        if verbose:
            print('Downloading {} to {}'.format(filename, folder))

        try:
            _download(alert, geom, filename, extension, folder)
        except Exception as e:
            msg = 'ERROR writing {}'.format(filename)
            if logger:
                logger.log(msg)
        else:
            msg = '{} downloaded to {}'.format(filename, folder)
            if logger:
                logger.log(msg)


def toDrive(site, date, folder, clas, limit=1, smooth='max',
            extension='GeoJSON', property_name=None,
            verbose=True, vector_mask=None, raster_mask=None,
            logger=None):
    """ Upload probable/confirmed alerts to Google Drive """
    if not utils.has_image(date, alerts.ALERTS).getInfo():
        msg = 'GLAD alerts not available for date {}'.format(date)
        if verbose:
            print(msg)
        if logger:
            logger.log(msg)
        return None

    date = ee.Date(date)

    if clas not in ['probable', 'confirmed']:
        clas = 'confirmed'

    name = '{}_alert_{}'.format(clas, date.format('yyyyMMdd').getInfo())

    try:
        geom = site.geometry()
    except:
        geom = site

    if isinstance(site, ee.FeatureCollection) and property_name:
        names = utils.get_options(site, property_name)
        names_cli = names.getInfo()
        for n in names_cli:

            # file name
            filename = '{}_{}'.format(name, n)

            # region
            region = site.filterMetadata(
                property_name, 'equals', n).first().geometry()

            # alert
            alert = FUNCTIONS[clas](region, date, limit, smooth)
            alert = mask(alert, vector_mask, raster_mask)

            # SKIP IF EMPTY ALERT
            count = utils.histogram(alert, clas, region).getInfo()
            if count == 0:
                msg = '{} has no alerts, skipping..'.format(filename)
                if verbose:
                    print(msg)
                if logger:
                    logger.log(msg)
                continue

            vector = utils.make_vector(alert, region)

            filename = filename.encode().decode('ascii', errors='ignore')

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
                continue
    elif isinstance(site, ee.Feature) and property_name:
        sitename = ee.String(site.get(property_name)).getInfo()
        # file name
        name = '{}_{}'.format(name, sitename)

        # alert
        alert = FUNCTIONS[clas](geom, date, limit, smooth)
        alert = mask(alert, vector_mask, raster_mask)

        # SKIP IF EMPTY ALERT
        count = utils.histogram(alert, clas, geom).getInfo()
        if count == 0:
            msg = '{} has no alerts'.format(name)
            if verbose:
                print(msg)
            if logger:
                logger.log(msg)
            return None

        vector = utils.make_vector(alert, geom)

        task = ee.batch.Export.table.toDrive(vector, name, folder, name,
                                             extension)
        task.start()
        msg = 'uploading {} to {} in GDrive'.format(name, folder)
        if verbose:
            print(msg)
        if logger:
            logger.log(msg)
    else:
        # alert
        alert = FUNCTIONS[clas](geom, date, limit, smooth)
        alert = mask(alert, vector_mask, raster_mask)

        # SKIP IF EMPTY ALERT
        count = utils.histogram(alert, clas, geom).getInfo()
        if count == 0:
            msg = '{} has no alerts'.format(name)
            if verbose:
                print(msg)
            if logger:
                logger.log(msg)
            return None

        vector = utils.make_vector(alert, geom)
        task = ee.batch.Export.table.toDrive(vector, name, folder, name,
                                             extension)
        task.start()
        msg = 'uploading {} to {} in GDrive'.format(name, folder)
        if verbose:
            print(msg)
        if logger:
            logger.log(msg)


def toAsset(site, date, folder, clas, limit=1, smooth='max',
            property_name=None, verbose=True, vector_mask=None,
            raster_mask=None, logger=None):
    """ Upload probable/confirmed alerts to Google Drive """
    if not utils.has_image(date, alerts.ALERTS).getInfo():
        msg = 'GLAD alerts not available for date {}'.format(date)
        if verbose:
            print(msg)
        if logger:
            logger.log(msg)
        return None

    user = ee.data.getAssetRoots()[0]['id']

    date = ee.Date(date)

    if clas not in ['probable', 'confirmed']:
        clas = 'confirmed'

    name = '{}_alert_{}'.format(clas, date.format('yyyyMMdd').getInfo())

    path = '{}/{}'.format(user, folder)

    try:
        geom = site.geometry()
    except:
        geom = site

    if isinstance(site, ee.FeatureCollection) and property_name:
        names = utils.get_options(site, property_name)
        names_cli = names.getInfo()
        for n in names_cli:

            # file name
            filename = '{}_{}'.format(name, n)

            # region
            region = site.filterMetadata(
                property_name, 'equals', n).first().geometry()

            # alert
            alert = FUNCTIONS[clas](region, date, limit, smooth)
            alert = mask(alert, vector_mask, raster_mask)

            # SKIP IF EMPTY ALERT
            count = utils.histogram(alert, clas, region).getInfo()
            if count == 0:
                msg = '{} has no alerts, skipping..'.format(filename)
                if verbose:
                    print(msg)
                if logger:
                    logger.log(msg)
                continue

            vector = utils.make_vector(alert, region)

            assetId = '{}/{}'.format(path, filename)

            try:
                task = ee.batch.Export.table.toAsset(vector, n, assetId)
                task.start()
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
                continue

    elif isinstance(site, ee.Feature) and property_name:
        # alert
        alert = FUNCTIONS[clas](geom, date, limit, smooth)
        alert = mask(alert, vector_mask, raster_mask)
        vector = utils.make_vector(alert, geom)
        sitename = ee.String(site.get(property_name)).getInfo()
        # file name
        filename = '{}_{}'.format(name, sitename)
        # assetId = '{}/{}'.format(path, filename)

        # SKIP IF EMPTY ALERT
        count = utils.histogram(alert, clas, geom).getInfo()
        if count == 0:
            msg = '{} has no alerts'.format(filename)
            if verbose:
                print(msg)
            if logger:
                logger.log(msg)
            return None

        gbatch.Export.table.toAsset(vector, path, filename)
        msg = 'uploading {} to {} in Assets'.format(filename, path)
        if verbose:
            print(msg)
        if logger:
            logger.log(msg)
    else:
        # alert
        alert = FUNCTIONS[clas](geom, date, limit, smooth)
        alert = mask(alert, vector_mask, raster_mask)
        vector = utils.make_vector(alert, geom)

        # SKIP IF EMPTY ALERT
        count = utils.histogram(alert, clas, geom).getInfo()
        if count == 0:
            msg = '{} has no alerts'.format(name)
            if verbose:
                print(msg)
            if logger:
                logger.log(msg)
            return None

        gbatch.Export.table.toAsset(vector, path, name)
        msg = 'uploading {} to {} in Assets'.format(name, path)
        if verbose:
            print(msg)
        if logger:
            logger.log(msg)
