    ::

        88888888888    d8888888b    888 .d8888b. 888888888888888888888888b.                d88888888888b.8888888
            888       d888888888b   888d88P  Y88b  888  888       888   Y88b              d88888888   Y88b 888
            888      d88P88888888b  888888    888  888  888       888    888             d88P888888    888 888
            888     d88P 888888Y88b 888888         888  8888888   888   d88P            d88P 888888   d88P 888
            888    d88P  888888 Y88b888888  88888  888  888       8888888P"            d88P  8888888888P"  888
            888   d88P   888888  Y88888888    888  888  888       888 T88b            d88P   888888        888
            888  d8888888888888   Y8888Y88b  d88P  888  888       888  T88b          d8888888888888        888
            888 d88P     888888    Y888 "Y8888P8888888888888888888888   T88b88888888d88P     888888      8888888


Description
=========================
A simple Python package to facilitate interactions with Tangier's SOAP API.

Overview
=========================
Tangier API is a client library for using Python to interact with the Tangier’s SOAP API.

Here, we will only be discussing methods that allow the user to perform queries from the API.
All of the necessary methods to Create and Update via the API are also available in this library, but they will not be
covered here.

You can check the API documentation for more information on those methods.


Installation
=============
to install the latest version, you can just run

.. code:: bash

    pip install tangier-api



Setup
======
You will need to have an active API account for Tangier and a config file that looks like the below

.. code:: text

    [tangier]
    username = api_user
    password = api_password
    schedule_endpoint = https://tangierweb.com/webservices/schedulerequest/schedulerequest.asmx?WSDL
    provider_endpoint = https://tangierweb.com/webservices/ProviderMaintenance/ProviderMaintenance.asmx?WSDL
    location_endpoint = https://tangierweb.com/webservices/LocationMaintenance/LocationMaintenance.asmx?WSDL
    testing_site = TESTING-SITE-ID
    testing_npi = 0000000000
    log_dir =

You can store this file anywhere, but you need to make its location known to the interpreter that calls the API via the
environment variable ``TANGIER_CONF_FILE``.

Usage
======

Logging In
-----------
.. code:: python

    import os
    os.environ['TANGIER_CONF_FILE'] = 'C:/path/to/tangier_api.conf'

    from tangier_api import ProviderConnection, LocationConnection, ScheduleConnection
    pconn = ProviderConnection()
    lconn = LocationConnection()
    sconn = ScheduleConnection()

That's it. You have three authenticated clients, one for each of these services.

Raw API Calls
-------------

Each of the above classes, ProviderConnection, LocationConnection, ScheduleConnection, im-
plement a direct connection to Tangier’s SOAP endpoints. That means you could just use raw
XML if you really wanted to. For example:

.. code:: python

    from tangier_api import settings
    import xmlmanip
    lconn = LocationConnection()
    xml = """
        <tangier version="1.0" method="location.request">
            <admin_user>{username}</admin_user>
            <admin_pwd>{password}</admin_pwd>
            <locations>
                <location action="info">
                    <site_id>{site_id}</site_id>
                </location>
            </locations>
        </tangier>
    """.format(
        username=settings.TANGIER_USERNAME,
        password=settings.TANGIER_PASSWORD,
        site_id="YOUR-SITE-ID"
    )

    response_xml = lconn.MaintainLocations(xml)
    xmlmanip.print_xml(response_xml)

This should make it fairly simple for you to write your own custom API calls if necessary.

Get Schedule
-------------

.. code:: python

    sconn = ScheduleConnection()

    # you can do this by emp_id or site_id
    response_xml = sconn.get_schedule(
        start_date='2018-01-01',
        end_date='2018-01-14',
        site_id='YOUR-SITE-ID'
    )
    # returns a list of xml strings, used in other methods
    response_xml_list = sconn.get_schedules(
        start_date='2018-01-01',
        end_date='2018-01-14',
        site_ids=['YOUR-SITE-ID']
    )
    # list of all of the shifts between the given dates for the given site ids
    scheduled_shifts = sconn.get_schedule_values_list(
        start_date='2018-01-01',
        end_date='2018-01-14',
        site_ids=['YOUR-SITE-ID', 'YOUR-SITE-ID-2']
    )

Provider Maintenance
--------------------
.. code:: python

    pconn = ProviderConnection()
    # returns xml corresponding to providers in Tangier with Primary Key in their Database of 1 and 2
    response_xml = pconn.get_provider_info(
        # do not include this variable if you want all_providers
        provider_ids=[1,2],
        # you should just use this all the time
        use_primary_keys=True,
        # bug, this field shouldn't be needed to prevent fetching of all but it is
        all_providers=False,
    )
    # wrapper around get_provider_info that returns a list of dicts instead of raw xml
    provider_list = pconn.provider_info_values_list(
        # do not include this variable if you want all_providers
        provider_ids=[1,2],
        # you should just use this all the time
        use_primary_keys=True,
        # bug, this field shouldn't be needed to prevent fetching of all but it is
        all_providers=False,
    )

Location Maintenance
---------------------
.. code:: python

    lconn = LocationConnection()
    response_xml = lconn.get_locations_info(
        # do not include variable if you want all sites
        site_ids=['CRMC-APP']
    )
    # no arguments means all sites in a list
    location_list = lconn.location_info_values_list()

I am not going to demonstrate any of the below, but you can see them in the
`API documentation <https://jjorissen52.github.io/tangier_api/py-modindex.html>`__  if necessary.

.. code:: python

    lconn.add_location
    lconn.update_location
    lconn.delete_location