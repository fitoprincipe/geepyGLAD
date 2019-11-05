## Global Forest Watch GLAD alerts using Google Earth Engine

More information about GLAD alerts in http://glad-forest-alert.appspot.com/

*Hansen, Matthew C., Alexander Krylov, Alexandra Tyukavina, Peter V. Potapov, Svetlana Turubanova, Bryan Zutta, Suspense Ifo, Belinda Margono, Fred Stolle, and Rebecca Moore. “Humid Tropical Forest Disturbance Alerts Using Landsat Data.” Environmental Research Letters 11, no. 3 (2016): 034008. https://doi.org/10.1088/1748-9326/11/3/034008.*

This code takes the GLAD alerts dataset available in Google Earth Engine and downloads a vector layer of the alerts for a desired period.

### Install in Linux

1. clone this repository: `git clone https://github.com/fitoprincipe/geepyGLAD`
2. get into the cloned repo: `cd geepyGLAD`
3. Install `virtualenv` if not installed: https://virtualenv.pypa.io/en/latest/installation/ 
3. Install:

```bash
$ virtualenv venv --python=python3
$ . venv/bin/activate
$ pip install --editable .
```

### Install in Windows

You can follow a similar approach to the Linux installation, but you'll need some previous work for which you can follow this guide: https://programwithus.com/learn-to-code/Pip-and-virtualenv-on-Windows/

Or, you can use [Anaconda](https://www.anaconda.com/).

1. Install Anaconda

2. Open Anaconda Prompt

3. Create a conda environment with python 3. Follow this guide: https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#creating-an-environment-with-commands

4. Be sure the environment is activated, the prompt should have the name of the newly created environment between parenthesis. For example, if the name of the environment is `geepy3` the prompt should look:

   ``` bash
   (geepy3) C:/>
   ```
   
5. If it is not activated, then activate:

   ``` bash
   (base) C:/>conda activate geepy3
   (geepy3) C:/>
   ```
   
6. clone this repository
   
   ``` bash   
   (geepy3) C:/>git clone https://github.com/fitoprincipe/geepyGLAD
   ```
   
7. get into the cloned repository
   ``` bash
   (geepy3) C:/>cd geepyGLAD
   (geepy3) C:/geepyGLAD>
   ```
   
8. Install this repository
   ``` bash   
   (geepy3) C:/geepyGLAD>pip install --editable .
   ```
   **NOTE**: The dot (.) is important
   
9. Install Earth Engine Python API
   ``` bash   
   (geepy3) C:/geepyGLAD>conda install -c conda-forge earthengine-api
   ```
10. Authenticate to Earth Engine
   ``` bash   
   (geepy3) C:/geepyGLAD>earthengine authenticate
   ```
### First time usage

After installation

1. navigate to a folder where you want to download the alerts. Must be different from the installation folder. For example, it could be `glad_alerts`:

``` bash
(geepy3) C:/geepyGLAD>cd ..
(geepy3) C:/>mkdir glad_alerts
(geepy3) C:/glad_alerts>
```

2. In that empty folder check if the installation was successful:

``` bash
(geepy3) C:/glad_alerts>glad --help
```
If installation was successful, this will prompt:
``` bash
Usage: glad [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  alert          Export GLAD alerts to Google Drive, Earth Engine Asset or...
  make-config    Create a configuration file (config.json)
  period         Export a period (from START to END) of GLAD alerts to...
  sites          Show available site names
  update-config  Update config.json.
  user           Show Earth Engine user and email
```

3. Create a configuration file

   ``` bash
   (geepy3) C:/glad_alerts>glad make-config
   ```

### Configuration

The configuration for this application is driven by `config.json` in the following way:

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

To modify the configuration file you can (carefully) modify the file `config.json` or you can do it safely using a cmd command:

``` bash
   (geepy3) C:/glad_alerts>glad update-config
```

To see the help for this command type
``` bash
   (geepy3) C:/glad_alerts>glad update-config --help
```

### Everyday usage

Suppose you just turned on your computer, what do you do?

1. Open Anaconda Prompt

2. Activate environment. For example,

   ``` bash
   (base) C:/>conda activate geepy3
   (geepy3) C:/>
   ```

3. navigate to alerts folder. For example,
   ``` bash
   (geepy3) C:/>cd glad_alerts
   (geepy3) C:/cd glad_alerts>
   ```

4.  If you already set up the configuration, the just run:
   ``` bash   
   (geepy3) C:/cd glad_alerts>glad alert
   ```
   To see the help for this command type
   ``` bash   
   (geepy3) C:/cd glad_alerts>glad alert --help
   ```