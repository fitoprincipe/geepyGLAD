# coding=utf-8

""" Main module for GLAD alerts """

import ee
import datetime
from . import utils
from geetools import tools

ALERTS = utils.cleanup_sa19(ee.ImageCollection('projects/glad/alert/UpdResult'))
TODAY = datetime.date.today()


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


def get_probable(site, date, limit=1, smooth='max'):
    """ Get the 'probable' mask for the given site and date """
    date = ee.Date(date)
    year = date.get('year')

    # limit from ha to m2
    limit = limit * 10000

    # filter collection up to selected date
    start = ee.Date.fromYMD(year, 1, 1)
    col = ALERTS.filterDate(ee.Date(start), date.advance(1, 'day'))

    # filter bounds
    col = col.filterBounds(site)

    # get loss
    loss = last_probable_mask(col, year)

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

    final = final_mask.addBands([smooth_alertDate, dateBand]).updateMask(final_mask)
    return final


def get_confirmed(site, date, limit=1, smooth='max'):
    date = ee.Date(date)
    year = date.get('year')

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

    return final_mask.addBands([dateBand, smooth_alertDate]).updateMask(final_mask)