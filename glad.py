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
    'saveTo': 'local'
}

HEADER = """Config file:

{}

Run command:

    {}
"""


# HELPERS
def load_config(name):
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


def initEE(logger=None):
    import ee
    try:
        ee.Initialize()
    except Exception as e:
        msg = "Couldn't connect to Earth Engine. Check your internet connection - {}".format(e)
        print(msg)
        if logger:
            logger.log(msg)
        raise e
    else:
        if logger:
            logger.log('Earth Engine initialized successfully')


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
    config = load_config('config.json')
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
@click.option('-m', '--mask', default=True, type=bool, help='Whether to use the mask in config file or not')
@click.option('-v', '--verbose', default=True, type=bool)
@click.option('--config', default=None, help='The name of the configuration file. Defaults to "config.json"')
def alert(savein, clas, date, site, mask, verbose, config):
    """ Export GLAD alerts to Google Drive, Earth Engine Asset or Local files.
    Takes configuration parameters from `config.json`.
    """
    # LOAD CONFIG FILE
    configname = config  # change variable name
    if not configname:
        configname = 'config.json'

    config = load_config(configname)
    if not config: return None

    # SITE PARAMS
    site_params = config['site']
    asset_path = site_params['assetPath']
    property_name = site_params['propertyName']
    usersite = site  # change variable name

    # SAVE PARAMS
    destination = savein or config['saveTo']
    save_params = config[destination]
    soptions = ['drive', 'asset', 'local']

    # DATE PARAMS
    if not date:
        date = config['date']
    alert_date = dt.today().isoformat() if date == 'today' else date

    # MIN AREA
    limit = config['minArea']

    # CLASS
    if not clas:
        clas = config['class']

    # RUN COMMAND AND HASH
    command = 'glad alert -s {} -c {} -d {} -m {} -v {}'.format(
        savein, clas, date, mask, verbose)
    if usersite:
        command += ' --site {}'.format(usersite)

    config_str = json.dumps(config, indent=2)
    tohash = '{} {}'.format(config_str, command)
    tohash = tohash.encode('utf-8')
    import hashlib
    h = hashlib.sha256()
    h.update(tohash)
    hexcode = h.hexdigest()
    logname = '{} {}'.format(date, hexcode)

    header = HEADER.format(config_str, command)

    # LOGGER
    from geepyGLAD.logger import Logger
    logdir = 'logs'
    logger = Logger(logname, logdir)

    logger.header(header)

    if destination not in soptions:
        msg = 'savein parameter must be one of {}'.format(soptions)
        logger.log(msg)
        print(msg)
        return None

    # INITIALIZE EE
    import ee
    initEE(logger)
    try:
        from geepyGLAD import utils, alerts, batch
    except Exception as e:
        msg = 'ERROR while importing geepyGLAD - {}'.format(e)
        logger.log(msg)
        raise e

    site = ee.FeatureCollection(asset_path)

    if usersite:
        site = site.filterMetadata(property_name, 'equals', usersite)
        site = ee.Feature(site.first())

    # Check for available alert image in the given date
    has_images = utils.has_image(alert_date, alerts.ALERTS).getInfo()
    if not has_images:
        msg = 'GLAD alerts not available for date {}'.format(date)
        logger.log(msg)
        print(msg)
        return None

    args = dict(
        site=site,
        date=alert_date,
        clas=clas,
        limit=limit,
        property_name=property_name,
        verbose=verbose,
        folder=save_params['folder'],
        logger=logger
    )

    raster_mask_id = config['rasterMask']
    if raster_mask_id and mask:
        raster_mask = ee.Image(raster_mask_id)
        args['raster_mask'] = raster_mask

    # COMPUTE ALERTS
    try:
        batch.download(**args, destination=destination)
    except Exception as e:
        msg = 'ERROR: {}'.format(str(e))
        logger.log(msg)
        raise e


if __name__ == '__main__':
    main()