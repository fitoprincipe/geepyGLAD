## Global Forest Watch GLAD alerts using Google Earth Engine

### Install

1. clone this repository: `git clone https://github.com/fitoprincipe/geepyGLAD`
2. get into the cloned repo: `cd geepyGLAD`
3. Install `virtualenv` if not installed: https://virtualenv.pypa.io/en/latest/installation/ 
3. Install:

```bash
$ virtualenv venv --python=python3
$ . venv/bin/activate
$ pip install --editable .
```

### Configuration

To configure this application modifying `config.json` the following way:

```
{
  "site": {
    "assetPath": "USDOS/LSIB_SIMPLE/2017", 
    "propertyName": "country_na"
  },

  "date": "today",

  "minArea": 1,

  "smooth": "max",
  
  "class": "both",

  "drive": {
    "folder": "GLAD_ALERTS",
    "format": "GeoJSON"
  },

  "asset": {
    "folder": "GLAD_ALERTS"
  },

  "local": {
    "folder": "alerts",
    "subfolders": "True",
    "format": "JSON"
  },
     
  "saveTo": "drive",
  
  "rasterMask": null,

  "vectorMask": null
}
```
- **assetPath**: the path of the asset that holds the boundaries to clip the 
alerts. See: https://developers.google.com/earth-engine/importing. For example,
for countries you can use `USDOS/LSIB_SIMPLE/2017`
- **propertyName**: the name of the property of the table that "divides" it.
For example, country names in the given table are in property named `country_na`
- **date**: date for the alert in format YYYY-MM-DD. If the word "today" is
parsed, it'll compute the alerts for the date when the script is run. This can
also be modified when running the script using parameter `-d` or  `--date`.
- **minArea**: the minimum area to include in results. The units are hectares.
- **smooth**: the smoothing method. Can be one of: `max`, `mode` or `none`.
- **class**: the class to compute. Can be one of `probable`, `confirmed` or `both`
- **drive**:
  - **folder**: Google Drive folder to save results. It cannot be a subfolder.
  It can only be a folder in root. If not present, it will be created.
  - **format**: one of "GeoJSON", "KML", "KMZ", or "SHP"
- **asset**:
  - **folder**: asset folder to save the results. It can be a subfolder. For
  example: `gfw/glad/alers`
- **local**:
  - **folder**: folder to download the results
  - **subfolders**: if `True` it will create subfolders with the name of each
  record (given by `propertyName`)
  - **format**: it can only be `JSON`
- **saveTo**: location to save the results. Can be one of `drive`, `asset` or
`local`
- **rasterMask**: the assetId for a raster mask
- **vectorMask**: the assetId for a vector mask (FeatureCollection)

### Run (help)
```bash
$ glad --help
```