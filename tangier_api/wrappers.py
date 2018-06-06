from functools import wraps
import xmlmanip

from . import exceptions


def debug_options(method):
    @wraps(method)
    def _impl(self, *method_args, **method_kwargs):
        if not method_args:
            raise exceptions.APICallError('argument "xml_string" must be provided to '
                                          'api.LocationConnection.MaintainLocations')
        if self.show_xml_request:
            xmlmanip.print_xml(method_args[0])
        # response = method_args[0]
        response = method(self, *method_args, **method_kwargs)
        if self.show_xml_response:
            xmlmanip.print_xml(response)
        return response
    return _impl


def handle_response(method):
    @wraps(method)
    def _impl(self, *method_args, **method_kwargs):
        response = method(self, *method_args, **method_kwargs)
        schema = xmlmanip.XMLSchema(response.encode('utf-8'))
        if schema.search(comment__contains='Error'):
            raise exceptions.APIError(schema.search(comment__contains='Error'))
        if schema.search(error__contains=''):
            raise exceptions.APIError(schema.search(error__contains=''))
        return response
    return _impl