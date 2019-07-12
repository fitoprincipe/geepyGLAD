# coding=utf-8

import ee
ee.Initialize()

import click
import geepyGLAD as glad
from datetime import date as dt
import json


@click.command()
@click.option('-s', '--savein', default=None, help='where to save the files. Takes default from config.json')
@click.option('-c', '--clas', default='both', help='The class to export. Can be "probable", "confirmed" or "both"')
@click.option('-d', '--date', default=None)
@click.option('--site', default=None)
@click.option('-v', '--verbose', default=True, type=bool)
def main(savein, verbose, clas, date, site):
    """ Export GLAD alerts to Google Drive, Earth Engine Asset or Local files.
    Takes configuration parameters from `config.json`.
    """
    # load config file
    with open('config.json', 'r') as conf:
        config = json.load(conf)

    if savein:
        destination = savein
    else:
        destination = config['saveTo']

    params = config[destination]

    # change variable name
    usersite = site

    # SITE
    site_params = config['site']
    assetpath = site_params['assetPath']
    propertyName = site_params['propertyName']

    site = ee.FeatureCollection(assetpath)

    if usersite:
        site = site.filterMetadata(propertyName, 'equals', usersite)

    if not date:
        date = config['date']

    alert_date = dt.today().isoformat() if date == 'today' else date

    limit = config['minArea']
    smooth = config['smooth']

    if clas == 'both':
        clas = ['probable', 'confirmed']
    else:
        clas = [clas]

    if not glad.utils.has_image(date, glad.alerts.ALERTS).getInfo():
        print('GLAD alerts not available for date {}'.format(date))
        return None

    for c in clas:
        if destination == 'drive':
            glad.batch.toDrive(site, alert_date, params['folder'], c, limit,
                               smooth, params['format'], propertyName, verbose)
        if destination == 'asset':
            glad.batch.toAsset(site, alert_date, params['folder'], c, limit,
                               smooth, propertyName, verbose)

        if destination == 'local':
            glad.batch.toLocal(site, alert_date, c, limit, smooth,
                               propertyName, params['folder'], params['format'],
                               params['subfolders'], verbose)


if __name__ == '__main__':
    main()