import unittest, sys
import moment, xmlmanip


def generate_empty_list_error_response(test, list_name):
    return f'During "{test}", returned {list_name} had a length of 0 indicating ' \
           f'an issue with the API call'


class TestImport(unittest.TestCase):
    def test_import(self):
        import tangier_api.api


class TestScheduleConnection(unittest.TestCase):
    def test_get_schedule(self):
        from tangier_api.api import ScheduleConnection, TESTING_SITE
        connection = ScheduleConnection()
        today = moment.utcnow().strftime("%Y-%m-%d")
        three_months_ago = moment.utcnow().add(months=-2).strftime("%Y-%m-%d")
        schedule = xmlmanip.XMLSchema(connection.get_schedule(site_id=TESTING_SITE,
                                                              start_date=three_months_ago,
                                                              end_date=today))
        schedule_list = schedule.search(location__contains='')
        self.assertTrue(len(schedule_list) != 0,
                        generate_empty_list_error_response(sys._getframe().f_code.co_name, 'schedule_list'))

    def test_get_schedules(self):
        from tangier_api.api import ScheduleConnection, TESTING_SITE
        connection = ScheduleConnection()
        today = moment.utcnow().strftime("%Y-%m-%d")
        three_months_ago = moment.utcnow().add(months=-2).strftime("%Y-%m-%d")

        schedules = connection.get_schedules(site_ids=[TESTING_SITE, TESTING_SITE],
                                             start_date=three_months_ago,
                                             end_date=today)
        for schedule in schedules:
            schedule_list = xmlmanip.XMLSchema(schedule).search(date__ne='')
            self.assertTrue(len(schedule_list) != 0,
                            generate_empty_list_error_response(sys._getframe().f_code.co_name, 'schedule_list'))

    def test_get_schedule_values_list(self):
        from tangier_api.api import ScheduleConnection, TESTING_SITE
        connection = ScheduleConnection()
        today = moment.utcnow().strftime("%Y-%m-%d")
        three_months_ago = moment.utcnow().add(months=-2).strftime("%Y-%m-%d")
        schedule_list = connection.get_schedule_values_list(site_ids=[TESTING_SITE, TESTING_SITE],
                                                            start_date=three_months_ago,
                                                            end_date=today)
        self.assertTrue(len(schedule_list) != 0,
                        generate_empty_list_error_response(sys._getframe().f_code.co_name, 'schedule_list'))


class TestProviderConnection(unittest.TestCase):
    def test_get_provider_info(self):
        from tangier_api.api import ProviderConnection, TESTING_NPI
        provider = ProviderConnection()
        provider_response = xmlmanip.XMLSchema(provider.get_provider_info(provider_ids=[TESTING_NPI]))
        provider_list = provider_response.search(emp_id__contains='')
        self.assertTrue(len(provider_list) != 0,
                        generate_empty_list_error_response(sys._getframe().f_code.co_name, 'provider_list'))

    def test_provider_info_values_list(self):
        from tangier_api.api import ProviderConnection, TESTING_NPI
        provider = ProviderConnection()
        provider_list = provider.provider_info_values_list(provider_ids=[TESTING_NPI])
        self.assertTrue(len(provider_list) != 0,
                        generate_empty_list_error_response(sys._getframe().f_code.co_name, 'provider_list'))


class TestAsyncScheduleConnection(unittest.TestCase):
    def test_async_get_schedules(self):
        from tangier_api.async_api import AsyncScheduleConnection
        from tangier_api.api import TESTING_SITE
        connection = AsyncScheduleConnection()
        today = moment.utcnow().strftime("%Y-%m-%d")
        three_months_ago = moment.utcnow().add(months=-2).strftime("%Y-%m-%d")
        site_ids = [TESTING_SITE*3]
        request_list = connection.generate_request_list(three_months_ago, today, site_ids)
        schedule_list = connection.get_schedules(request_list)
        self.assertTrue(len(schedule_list) != 0,
                        generate_empty_list_error_response(sys._getframe().f_code.co_name, 'schedule_list'))


if __name__ == "__main__":
    unittest.main()
