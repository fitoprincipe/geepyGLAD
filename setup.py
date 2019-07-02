from setuptools import setup

setup(
    name='ipygeeGLAD',
    version='0.0.1',
    py_modules=['glad'],
    install_requires=[
        'Click',
        'earthengine-api',
        'oauth2client',
        'geetools'
    ],
    entry_points='''
        [console_scripts]
        glad=glad:main
    ''',
)