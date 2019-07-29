# coding=utf-8
import ee
try:
    ee.Initialize()
except:
    print("Couldn't connect to Earth Engine. Check your internet connection")

import click
import geepyGLAD as glad
from datetime import date as dt
import json
import os

@click.group()
def main():
    pass

@main.command()
def user():
    """ Show Earth Engine user and email """
    uid = ee.data.getAssetRoots()[0]['id']
    email = ee.data.getAssetAcl(uid)['owners'][0]
    us = uid.split('/')[1]
    print('User: {}\nEmail: {}'.format(us, email))
    return None

@main.command()
@click.option('-s', '--savein', default=None, help='where to save the files. Takes default from config.json')
@click.option('-c', '--clas', default=None, help='The class to export. Can be "probable", "confirmed" or "both"')
@click.option('-d', '--date', default=None, help='If this param is not set, it will use the date for today')
@click.option('--site', default=None, help='The name of the site to process, must be present in the parsed property')
@click.option('-m', '--mask', default=None, help='The mask to apply to the final result. Can be None, "raster" or "vector"')
@click.option('-v', '--verbose', default=True, type=bool)
def alert(savein, verbose, clas, date, site, mask):
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

    soptions = ['drive', 'asset', 'local']

    if destination not in soptions:
        return 'savein parameter must be one of {}'.format(soptions)

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

    # Mask
    vector_mask_id = config['vectorMask']
    if vector_mask_id:
        vector_mask = ee.FeatureCollection(vector_mask_id)
    raster_mask_id = config['rasterMask']
    if raster_mask_id:
        raster_mask = ee.Image(raster_mask_id)

    if not clas:
        clas = config['class']

    if clas == 'both':
        clas = ['probable', 'confirmed']
    else:
        clas = [clas]

    has_images = glad.utils.has_image(alert_date, glad.alerts.ALERTS).getInfo()

    if not has_images:
        print('GLAD alerts not available for date {}'.format(date))
        return None

    for c in clas:
        args = dict(
            site=site,
            date=alert_date,
            clas=c,
            limit=limit,
            smooth=smooth,
            property_name=propertyName,
            verbose=verbose,
            folder=params['folder'],
        )

        # create log file
        logname = '{}{}_{}_{}_{}m2.txt'.format(
            '_'.join(assetpath.split('/')[2:]),
            '_'+propertyName or '_',
            c,
            alert_date,
            limit
        )
        logpath = os.path.join('logs', logname)

        if os.path.isfile(logpath):
            perm = 'a'
        else:
            perm = 'w+'

        if mask == 'raster':
            args['raster_mask'] = raster_mask
        elif mask == 'vector':
            args['vector_mask'] = vector_mask

        try:
            if destination == 'drive':
                msgs = glad.batch.toDrive(**args)
            if destination == 'asset':
                msgs = glad.batch.toAsset(**args)
            if destination == 'local':
                args['subfolders'] = params['subfolders']
                msgs = glad.batch.toLocal(**args)
        except Exception as e:
            msgs = [str(e)]

        # write log
        with open(logpath, perm) as log:
            finalmsg = '\n'.join(msgs)
            log.write(finalmsg)

if __name__ == '__main__':
    main()