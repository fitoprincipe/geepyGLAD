# coding=utf-8

""" Util functions for GLAD alerts """

import ee
from geetools import tools
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


def get_days(month, year, collection=None):
    """ Get days available for the given month and year """
    if collection is None:
        collection = cleanup_sa19(ee.ImageCollection('projects/glad/alert/UpdResult'))

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


def has_image(date, collection):
    """ Returns True if there is at least one image for the parsed date in the
    parsed collection

    Is a server side code, so it returns a server side `True`
    (use `getInfo` to retrieve it)
    """
    d = ee.Date(date)
    dates = collection.toList(collection.size()).map(
        lambda img: ee.Image(img).date())

    return ee.List(dates).contains(d)


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
    area = ee.Image.pixelArea().rename('area')

    # image = bool_image.addBands(area)
    conn = bool_image.connectedPixelCount(1000).rename('connected')
    finalarea = area.multiply(conn)

    # get holes and islands
    island = bool_image.eq(1).And(finalarea.lte(limit))
    holes = bool_image.eq(0).And(finalarea.lte(limit))

    # fill holes
    filled = bool_image.where(holes, 1)
    # get rid island
    no_island = filled.where(island, 0)

    return no_island


def get_rid_islands(bool_image, limit, scale=30, eightConnected=False):
    """ Get rid of 'islands' and 'holes' less than the given limit param.

    :param bool_image: The boolean image that will be use to detect islands and
        holes. It must be boolean (ones and zeros)
    :param limit: all islands and holes less than this limit will be erased.
        This must be in m2.
    """
    area = ee.Image.pixelArea().rename('area')

    scale = ee.Number(scale)
    limit = ee.Number(limit)

    count = limit.divide(scale.pow(2)).multiply(1.1)
    count = count.round()

    conn = bool_image.connectedPixelCount(512, eightConnected).rename('connected')
    finalarea = area.multiply(conn)

    # get holes and islands
    island = bool_image.eq(1).And(finalarea.lte(limit))

    # get rid island
    no_island = bool_image.where(island, 0)

    finalarea = finalarea.updateMask(no_island).unmask()

    return no_island.addBands(finalarea)


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


def make_alerts_vector(alerts, region):
    """ accepts the result from alerts.period function """
    # band names
    year = ee.Number(alerts.get('year'))
    yearStr = year.format().slice(2,4)
    dateB = ee.String('alertDate').cat(yearStr)
    confB = ee.String('confirmed').cat(yearStr)
    probB = ee.String('probable').cat(yearStr)
    confDB = ee.String('confirmedDate').cat(yearStr)
    probDB = ee.String('probableDate').cat(yearStr)

    # period
    start = ee.String(alerts.get('start_period'))
    end = ee.String(alerts.get('end_period'))

    # confirmed
    confmask = alerts.select([confB])
    confirmed = alerts.updateMask(confmask).select([dateB, confB, probDB, confDB])

    # probable
    probmask = alerts.select([probB])
    probable = alerts.updateMask(probmask).select([dateB, probB, probDB, confDB])

    # make individual vectors
    vconf = make_vector(confirmed, region).map(
        lambda feat: feat.set('class', 'confirmed'))
    vprob = make_vector(probable, region).map(
        lambda feat: feat.set('class', 'probable'))

    def extractDate(d):
        condition = d.neq(0)
        def true(date):
            datestr = ee.String(date.format())
            y = datestr.slice(0, 4)
            m = datestr.slice(4, 6)
            d = datestr.slice(6, 8)
            pattrn = '{y}-{m}-{d}'
            replace = {'y':y, 'm':m, 'd':d}
            return tools.string.format(pattrn, replace)
        def false(date):
            return date.format()

        return ee.String(ee.Algorithms.If(condition, true(d), false(d)))

    def updateDate(feat):
        feat = feat.set('start_period', start).set('end_period', end)
        date = extractDate(ee.Number(feat.get('label')))
        confBand = extractDate(ee.Number(feat.get(confDB)))
        probBand = extractDate(ee.Number(feat.get(probDB)))
        feat = feat.set(dateB, date)
        feat = feat.set(confDB, confBand)
        feat = feat.set(probDB, probBand)
        props = ee.List(['class', dateB, confDB, probDB,
                         'start_period','end_period', 'area_m2'])
        return feat.select(props)

    return vconf.merge(vprob).map(updateDate)


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


def get_bands(image, year=None):
    """ Get confY and alertDateY bands from the given image """
    if year:
        year = ee.Algorithms.String(int(year))
    else:
        d = image.date()
        yearInt = ee.Number(d.get('year'))
        year = ee.Algorithms.String(yearInt)
    yearStr = year.slice(2, 4)

    confband = tools.string.format('conf{y}', {'y': yearStr})
    dateband = tools.string.format('alertDate{y}', {'y': yearStr})

    return ee.Dictionary(dict(conf=confband, alertDate=dateband, suffix=yearStr))


def compute_breaks(col, year=None):
    last = tools.imagecollection.getImage(col, -1)
    bands = get_bands(last, year)
    band = ee.String(bands.get('conf'))
    suffix = ee.String(bands.get('suffix'))
    prob = ee.String('probableDate').cat(suffix)
    conf = ee.String('confirmedDate').cat(suffix)
    det = ee.String('detectedDate').cat(suffix)

    def makeBands(img):
        probDate = tools.image.emptyCopy(img.select(0)).rename(prob)
        confDate = tools.image.emptyCopy(img.select(0)).rename(conf)
        detectedDate = tools.image.emptyCopy(img.select(0)).rename(det)
        return img.addBands([probDate, confDate, detectedDate])

    col = col.map(makeBands)

    collist = col.toList(col.size())

    def wrap(img, accum):
        img = ee.Image(img)
        accum = ee.List(accum)
        before = ee.Algorithms.If(accum.size().eq(0),
                                  ee.Image(collist.get(0)),
                                  ee.Image(accum.get(-1)))
        before = ee.Image(before)
        diff = img.select(band).subtract(before.select(band)).rename('break')
        probable = diff.eq(2)
        confirmed = diff.eq(1)
        detected = probable.Or(confirmed)
        dateband = tools.date.makeDateBand(img)
        probdate = dateband.where(probable.Not(), before.select(prob)).rename(prob)
        confdate = dateband.where(confirmed.Not(), before.select(conf)).rename(conf)
        detecteddate = dateband.where(detected.Not(), before.select(det)).rename(det)
        newi = img.addBands([probdate, confdate, detecteddate], overwrite=True)
        return accum.add(newi)

    collist = ee.List(collist.iterate(wrap, ee.List([])))
    return ee.ImageCollection.fromImages(collist)