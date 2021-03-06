# coding=utf-8

""" Main module for GLAD alerts """

import ee
import datetime
from . import utils
from geetools import tools

ALERTS = utils.cleanup_sa19(ee.ImageCollection('projects/glad/alert/UpdResult'))
TODAY = datetime.date.today()


def proxy(image):
    """ Make a proxy (empty) image with the same bands as the parsed image """
    unmasked = image.unmask()
    return unmasked.where(unmasked.neq(0), 0).selfMask()


def get_images(collection, year):
    """ Get last 2 images of the given collection and date band of the last
    image """
    # build band names
    year = ee.Number(year).format()
    suffix = year.slice(2)

    bandname = ee.String('conf').cat(suffix)
    datebandname = ee.String('alertDate').cat(suffix)

    last2 = collection.limit(2, 'system:time_start', False)
    last2list = last2.toList(2)

    replace = ee.Dictionary({})\
                .set(bandname, 'alert')\
                .set(datebandname, 'alert_doy')

    # Last image
    last = ee.Image(last2list.get(0))
    last = tools.image.renameDict(last, replace)

    # Image before last image
    before = ee.Image(last2list.get(1))
    before = tools.image.renameDict(before, replace)

    return last, before


def last_confirmed_mask(collection, year):
    """ Get the latest confirmed mask from the given collection and year """
    last, before = get_images(collection, year)

    last_alert = last.select('alert')
    before_alert = before.select('alert')

    # It's confirmed when last is 3 and befores is 2
    confirmed = last_alert.eq(3).And(before_alert.eq(2)).rename('confirmed')

    return last.addBands(confirmed).updateMask(confirmed).unmask()


def last_probable_mask(collection, year):
    """ Get the latest probable mask from the given collection and year """

    last, before = get_images(collection, year)

    last_alert = last.select('alert')
    before_alert = before.select('alert')

    probable = last_alert.eq(2).And(before_alert.eq(0)).rename('probable')
    return last.addBands(probable).updateMask(probable).unmask()


def get_probable_OLD(site, date, limit=1, smooth='max'):
    """ Get the 'probable' mask for the given site and date """
    try:
        site = site.geometry()
    except:
        pass

    date = ee.Date(date)
    year = date.get('year')
    month = date.get('month')
    day = date.get('day')

    # filter collection up to selected date
    start = ee.Date.fromYMD(year, 1, 1)
    col = ALERTS.filterDate(ee.Date(start), date.advance(1, 'day'))

    # filter bounds
    col = col.filterBounds(site)

    loss = last_probable_mask(col, year)

    # clip loss
    loss = loss.clip(site)

    # loss mask
    loss_mask = loss.select('probable')

    # observation date
    alertDate = loss.select('alert_doy')

    # get rid of min area
    final_mask = utils.get_rid_min_area(loss_mask, limit)

    # smooth
    final_mask = utils.smooth(final_mask, smooth)

    # add doy band
    smooth_alertDate = utils.smooth(alertDate, 'max').rename('alert_doy')

    # add date band
    dateBand =  tools.image.doyToDate(smooth_alertDate).rename('alert_date')

    final = final_mask.addBands([smooth_alertDate, dateBand])

    final_masked = final.updateMask(final_mask)

    # get days
    days = utils.get_days(month, year, col)

    return ee.Image(ee.Algorithms.If(days.contains(day), final_masked,
                                     proxy(final)))


def get_confirmed_OLD(site, date, limit=1, smooth='max'):
    date = ee.Date(date)
    year = date.get('year')
    month = date.get('month')
    day = date.get('day')

    # filter collection up to selected date
    start = ee.Date.fromYMD(year, 1, 1)
    col = ALERTS.filterDate(ee.Date(start), date.advance(1, 'day'))

    col = col.filterBounds(site)

    # get mask
    loss = last_confirmed_mask(col, year)

    # get rid of min area
    final_mask = utils.get_rid_min_area(loss.select('confirmed'), limit)

    # smooth
    final_mask = utils.smooth(final_mask, smooth)

    # mask doy
    doy = loss.select('alert_doy')

    # focal_max doy
    smooth_alertDate = utils.smooth(doy, smooth)

    # add date band
    dateBand =  tools.image.doyToDate(smooth_alertDate).rename('alert_date')

    final = final_mask.addBands([dateBand, smooth_alertDate])

    final_masked = final.updateMask(final_mask)

    # get days
    days = utils.get_days(month, year, col)

    return ee.Image(ee.Algorithms.If(days.contains(day), final_masked,
                                     proxy(final)))


def period(start, end, site, limit, year=None, eightConnected=False,
           useProxy=False, mask=None):
    """ Compute probable and confirmed alerts over a period

    :param start: the start date of the period
    :param end: the end date of the period (inclusive)
    :param site: the site
    :type site: ee.Geometry or ee.Feature or ee.FeatureCollection
    :param limit: the minimum area to be computed
    :param year: the year to compute. If None takes the year from the date of
        the last available image
    :param eightConnected: parameter to pass to ee.Kernel
    :param useProxy: if True, includes alerts that did not change over the
        given period, but were alerts before the start date. Therefore, those
        alerts will not have a valid confirmedDate or probableDate (both will
        be 0). Also, alertDate will be before start_period property
    :param mask: a mask to apply to results. Typically a forest mask. If a
        string is passed, it will try to load it as an Image asset
    :type mask: ee.Image or str
    """
    if isinstance(site, (ee.Feature, ee.FeatureCollection)):
        region = site.geometry()
    else:
        region = site

    start = ee.Date(start)
    end = ee.Date(end).advance(1, 'day')

    filtered = ALERTS.filterBounds(region)

    if mask:
        if isinstance(mask, (ee.Image,)):
            maski = mask
        else:
            maski = ee.Image(mask)
        filtered = filtered.map(lambda img: img.updateMask(maski))

    sort = filtered.sort('system:time_start', True) # sort ascending
    filteredDate = sort.filterDate(start, end)

    filteredDate = utils.compute_breaks(filteredDate, year)

    # always get a last image
    last = ee.Image(tools.imagecollection.getImage(filteredDate, -1))
    period_first = ee.Image(filteredDate.first())

    bands = utils.get_bands(last, year)
    confband = ee.String(bands.get('conf'))
    dateband = ee.String(bands.get('alertDate'))
    yearStr = ee.String(bands.get('suffix'))
    if not year:
        yearInt = ee.Number(end.get('year')).toInt()
    else:
        yearInt = ee.Number(year).toInt()

    if useProxy:
        proxy = tools.image.empty(0, last.bandNames())
        first = proxy.copyProperties(source=last,
                                     properties=['system:footprint']) \
                     .set('system:time_start', start.millis())
        first = ee.Image(first)
    else:
        first = period_first

    firstconf = first.select(confband)
    lastconf = last.select(confband)

    diff = lastconf.subtract(firstconf)

    probname = ee.String('probable').cat(yearStr)
    confname = ee.String('confirmed').cat(yearStr)

    probable = diff.eq(2).rename(probname)
    confirmed = diff.eq(1).Or(diff.eq(3)).rename(confname)

    probable = utils.get_rid_islands(probable, limit, eightConnected)
    confirmed = utils.get_rid_islands(confirmed, limit, eightConnected)

    area_probable = probable.select('area')
    area_confirmed = confirmed.select('area')

    probable = probable.select(probname).selfMask()
    confirmed = confirmed.select(confname).selfMask()

    area = area_probable.add(area_confirmed)
    mask = area.gt(0)
    area = area.updateMask(mask)

    date = tools.image.doyToDate(
        last.select(dateband), year=yearInt).rename(ee.String('alertDate').cat(yearStr))
    date = date.updateMask(mask)

    # detected
    detected = last.select(ee.String('detectedDate').cat(yearStr))
    detected = detected.updateMask(mask)

    # probable
    probD = last.select(ee.String('probableDate').cat(yearStr))
    probD = probD.updateMask(mask)

    # confirmed
    confD = last.select(ee.String('confirmedDate').cat(yearStr))
    confD = confD.updateMask(mask)

    final = probable.addBands([confirmed, area, date, detected, probD, confD])
    dateformat = 'Y-MM-dd'

    return final.set('start_period', period_first.date().format(dateformat)) \
        .set('end_period', last.date().format(dateformat)) \
        .set('year', yearInt)


def oneday(site, date, limit=500, year=None, eightConnected=False, mask=None):
    """ Compute alerts for one day. Takes the last available alerts and the
    alerts 1 step before """
    date = ee.Date(date)

    if isinstance(site, (ee.Feature, ee.FeatureCollection)):
        region = site.geometry()
    else:
        region = site

    col = ALERTS.filterBounds(region)
    col = col.filterDate(ee.Date('1970-01-01'), date.advance(1, 'day'))

    last = tools.imagecollection.getImage(col, -1)
    before = tools.imagecollection.getImage(col, -2)

    return period(before.date(), last.date().advance(1,'day'), site, limit,
                  year, eightConnected=eightConnected, mask=mask)


def get_probable(site, date, limit=500, eightConnected=False, mask=None):
    """ Get only probable alerts """
    alerts = oneday(site, date, limit, eightConnected, mask)
    probable_mask = alerts.select('probable')
    return alerts.updateMask(probable_mask)


def get_confirmed(site, date, limit=500, eightConnected=False, mask=None):
    """ Get only confirmed alerts """
    alerts = oneday(site, date, limit, eightConnected, mask)
    probable_mask = alerts.select('confirmed')
    return alerts.updateMask(probable_mask)
