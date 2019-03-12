import os 
import configparser
import datetime

ENV_CONF_FILE = os.environ.get('TANGIER_CONF_FILE')
ENV_CONF_REGION = os.environ.get('TANGIER_CONF_REGION')
DEBUG = os.environ.get('TANGIER_DEBUG')
CONF_FILE = ENV_CONF_FILE if ENV_CONF_FILE else None
CONF_REGION = ENV_CONF_REGION if ENV_CONF_REGION else 'tangier'

DEFAULTS = {
    'username': None,
    'password': None,
    'schedule_endpoint': None,
    'provider_endpoint': None,
    'location_endpoint': None,
    'testing_site': None,
    'testing_npi': None,
    'log_dir': None,
    'debug': DEBUG,
}


def read_config(keys):
    """
    We don't want a failed import for bad config, we just want to set everything that is not in the config file/region
    set to None
    :param keys: (iterable) default keys to set to None
    :return:
    """
    config = configparser.ConfigParser(defaults=DEFAULTS, allow_no_value=True)
    config.read(CONF_FILE)
    if not config.has_section(CONF_REGION):
        config.add_section(CONF_REGION)

    parameters = {key: config.get(CONF_REGION, key) for key in keys}
    parameters.update({'config': config})
    return parameters


config_dict = read_config(DEFAULTS.keys())


TANGIER_USERNAME = config_dict.get('username')
TANGIER_PASSWORD = config_dict.get('password')
SCHEDULE_ENDPOINT = config_dict.get('schedule_endpoint')
PROVIDER_ENDPOINT = config_dict.get('provider_endpoint')
LOCATION_ENDPOINT = config_dict.get('location_endpoint')
TESTING_SITE = config_dict.get('testing_site')
TESTING_NPI = config_dict.get('testing_npi')
LOG_DIR = config_dict.get('log_dir')
now = datetime.datetime.now()