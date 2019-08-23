# coding=utf-8
import click
from datetime import date as dt
import json
import os

CONFIG = {
    'class': 'both',
    'site': {
        'assetPath': '',
        'propertyName': ''
    },
    'date': 'today',
    'minArea': 1000, # m2
    'vectorMask': '',
    'rasterMask': '',
    'drive': {
        'folder': 'gladAlerts',
        'format': 'GeoJSON'
    },
    'asset': {
        'folder': 'gladAlerts'
    },
    'local': {
        'folder': 'alerts',
        'subfolders': True,
        'format': 'JSON'
    },
    'saveTo': 'drive'
}

# HELPERS
def check_config(name):
    exists = os.path.isfile(name)
    if exists:
        # load config file
        with open(name, 'r') as conf:
            config = json.load(conf)
    else:
        msg = "Configuration file {} doesn't exist, to make it "\
              "run:\n\nglad make-config\n"
        print(msg.format(name))
        config = None
    return config


def initEE():
    import ee
    try:
        ee.Initialize()
    except Exception as e:
        print("Couldn't connect to Earth Engine."
              " Check your internet connection")
        raise e


@click.group()
def main():
    pass


@main.command()
def make_config():
    """ Create a configuration file (config.json) """
    def create(name):
        with open(name, 'w') as f:
            json.dump(CONFIG, f, indent=2)

    fname = 'config.json'

    exists = os.path.isfile(fname)
    if exists:
        msg = 'Configuration file already exists, do you really want ' \
              'to overwrite it? (y/n)'
        really = click.prompt(msg, type=bool, default=False)
        if really: create(fname)
    else:
        create(fname)


@main.command()
@click.argument('parameter')
@click.argument('value')
def update_config(parameter, value):
    """ Update config.json. Options are:

    - sitePath: the Asset path of the site to process\n
    - siteProperty: the name of the property that holds the name of the sites\n
    - date: date to process\n
    - minArea: minimum area in square meters\n
    - vectorMask: the Asset path of the mask (ee.FeatureCollection) to apply\n
    - rasterMask: the Asset path of the mask (ee.Image) to apply\n
    - driveFolder: the folder name to upload the results to Google Drive\n
    - driveFormat: the format for the file to upload to Google Drive\n
    - assetFolder: the Asset path to upload the results\n
    - localFolder: the local folder to download the results\n
    - localFormat: the file format to download the results\n
    - localSub: if True creates subfolders for each site (given by siteProperty)\n
    - saveTo: where to save results (drive, asset or local)\n
    """
    endpoints = {
        'class': ['class'],
        'sitePath': ['site', 'assetPath'],
        'siteProperty': ['site', 'propertyName'],
        'date': ['date'],
        'minArea': ['minArea'],
        'vectorMask': ['vectorMask'],
        'rasterMask': ['rasterMask'],
        'driveFolder': ['drive', 'folder'],
        'driveFormat': ['drive', 'format'],
        'assetFolder': ['asset', 'folder'],
        'localFolder': ['local', 'folder'],
        'localFormat': ['local', 'format'],
        'localSub': ['local', 'subfolders'],
        'saveTo': ['saveTo']
    }

    fname = 'config.json'
    exists = os.path.isfile(fname)
    if not exists:
        make_config()

    # load config file
    with open('config.json', 'r') as conf:
        config = json.load(conf)

    endpoint = endpoints.get(parameter)
    if endpoint:
        upd = config
        for end in endpoint:
            v = upd[end]
            if (not isinstance(v, dict)):
                upd[end] = value
            else:
                upd = v

        with open(fname, 'w') as f:
            json.dump(config, f, indent=2)

    else:
        print('parameter {} not available'.format(parameter))


@main.command()
def user():
    """ Show Earth Engine user and email """
    import ee
    try:
        ee.Initialize()
    except:
        print("Couldn't connect to Earth Engine. Check your internet connection")

    uid = ee.data.getAssetRoots()[0]['id']
    email = ee.data.getAssetAcl(uid)['owners'][0]
    us = uid.split('/')[1]
    msg = 'User: {}\nEmail: {}'.format(us, email)
    print(msg)


@main.command()
def sites():
    """ Show available site names """
    import ee
    initEE()
    config = check_config('config.json')
    if not config: return None

    siteAP = config['site']['assetPath']
    site = ee.FeatureCollection(siteAP)
    prop = config['site']['propertyName']

    options = site.aggregate_array(prop)
    print(options.getInfo())


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
    config = check_config('config.json')
    if not config: return None

    import ee
    initEE()
    import geepyGLAD as glad

    destination = savein or config['saveTo']

    soptions = ['drive', 'asset', 'local']

    if destination not in soptions:
        return 'savein parameter must be one of {}'.format(soptions)

    save_params = config[destination]

    # change variable name
    usersite = site

    # SITE
    site_params = config['site']
    asset_path = site_params['assetPath']
    property_name = site_params['propertyName']

    site = ee.FeatureCollection(asset_path)

    if usersite:
        site = site.filterMetadata(property_name, 'equals', usersite)

    if not date:
        date = config['date']

    alert_date = dt.today().isoformat() if date == 'today' else date

    limit = config['minArea']

    if not clas:
        clas = config['class']

    # Check for available alert image in the given date
    has_images = glad.utils.has_image(alert_date, glad.alerts.ALERTS).getInfo()
    if not has_images:
        print('GLAD alerts not available for date {}'.format(date))
        return None

    args = dict(
        site=site,
        date=alert_date,
        clas=clas,
        limit=limit,
        # smooth=smooth,
        property_name=property_name,
        verbose=verbose,
        folder=save_params['folder'],
    )

    # CREATE LOG FILE
    logname = '{}{}_{}_{}_{}m2.txt'.format(
        '_'.join(asset_path.split('/')[2:]),
        '_'+property_name or '_',
        clas,
        alert_date,
        limit
    )
    logdir = 'logs'

    if not os.path.isdir(logdir):
        os.mkdir(logdir)
    logpath = os.path.join(logdir, logname)

    if os.path.isfile(logpath):
        perm = 'a'
    else:
        perm = 'w+'

    # MASK
    vector_mask_id = config['vectorMask']
    if vector_mask_id:
        vector_mask = ee.FeatureCollection(vector_mask_id)
        args['vector_mask'] = mask or vector_mask

    raster_mask_id = config['rasterMask']
    if raster_mask_id:
        raster_mask = ee.Image(raster_mask_id)
        args['raster_mask'] = mask or raster_mask

    # COMPUTE ALERTS
    try:
        if destination == 'drive':
            msgs = glad.batch.toDrive(**args)
        if destination == 'asset':
            msgs = glad.batch.toAsset(**args)
        if destination == 'local':
            args['subfolders'] = save_params['subfolders']
            msgs = glad.batch.toLocal(**args)
    except Exception as e:
        raise e
        msgs = [str(e)]

    # write log
    with open(logpath, perm) as log:
        finalmsg = '\n'.join(msgs)
        log.write(finalmsg)


if __name__ == '__main__':
    main()