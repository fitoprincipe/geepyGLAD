# coding=utf-8

""" Util functions for GLAD alerts """

import ee
import math


def cleanup_sa19(collection):
    """ South America alerts for 2019 have an image that should not be
    there """
    def wrap(img, l):
        l = ee.List(l)
        theid = img.id()
        return ee.Algorithms.If(theid.compareTo('01_01_SBRA'), l.add(img), l)

    alerts = ee.List(collection.iterate(wrap, ee.List([])))
    alerts = ee.ImageCollection.fromImages(alerts)
    return alerts


def get_days(collection, month, year):
    """ Get days available for the given month and year """
    def wrap(img):
        d = img.date()
        m = d.get('month')
        y = d.get('year')
        return img.set('MONTH', m, 'YEAR', y)

    col_date = collection.map(wrap)

    filtered = col_date.filterMetadata(
        'MONTH', 'equals', month).filterMetadata('YEAR', 'equals', year)

    def iteration(img, l):
        l = ee.List(l)
        img = ee.Image(img)
        d = img.date().get('day')
        return l.add(d)

    days = ee.List(filtered.iterate(iteration, ee.List([]))).sort()
    days_str = days.map(lambda d: ee.Number(d))

    return days_str.distinct()


def get_pixel_limit(area, scale):
    """ Return number of pixels in the given area (m2) for the given scale """
    area = ee.Number(area).multiply(10000)
    scale = ee.Number(scale)
    return area.divide(scale.multiply(scale)).floor()


def get_rid_min_area(bool_image, limit):
    """ Get rid of 'islands' and 'holes' less than the given limit param.

    :param bool_image: The boolean image that will be use to detect islands and
        holes. It must be boolean (ones and zeros)
    :param limit: all islands and holes less than this limit will be erased.
        This must be in m2.
    """
    pixel_limit = get_pixel_limit(limit,
                                  bool_image.projection().nominalScale())

    # get connected pixels
    conn = bool_image.connectedPixelCount(1000).rename('connected')

    # get holes and islands
    island = bool_image.eq(1).And(conn.lte(pixel_limit))
    holes = bool_image.eq(0).And(conn.lte(pixel_limit))

    # fill holes
    filled = bool_image.where(holes, 1)
    # get rid island
    no_island = filled.where(island, 0)

    return no_island


def smooth(image, algorithm='max'):
    """ Get the smooth algorithms given its name """
    algs = {
        'max': ee.Image.focal_max,
        'mode': ee.Image.focal_mode,
        'none': ee.Image,
    }
    result = algs[algorithm](image)

    return result.set('system:time_start', image.date().millis())


def histogram(alert, clas, region=None):
    """ Return the number of pixels equal one in the given region """
    if not region:
        region = alert.geometry()

    result = alert.select(clas).reduceRegion(**{
        'reducer': ee.Reducer.fixedHistogram(0, 2, 2),
        'geometry': region,
        'scale': alert.projection().nominalScale(),
        'maxPixels': 1e13
    })

    result = result.get(clas)
    count = ee.Number(ee.Algorithms.If(
        result, ee.Array(result).get([1, 1]), 0))
    return count


def make_vector(image, region):
    """ Vectorize the given image in the given region """
    reducer = ee.Reducer.max()
    vector = image.reduceToVectors(**{
        'geometry': region,
        'reducer': reducer,
        'scale': image.select([0]).projection().nominalScale(),
        'maxPixels': 1e13
    })
    vector = vector.map(lambda feat: feat.set('area_m2',
                                              feat.geometry().area(1)))
    return vector


def dateFromDatetime(dt):
    """ ee.Date from datetime """
    return ee.Date(dt.isoformat())


def get_options(featureCollection, propertyName):
    """ get a list of all names in property name """
    def wrap(feat, l):
        l = ee.List(l)
        return l.add(feat.get(propertyName))

    options = featureCollection.iterate(wrap, ee.List([]))

    return ee.List(options).distinct()