import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from xmlmanip import XMLSchema


class BadSchemaError(BaseException):
    pass


class BadTagError(BaseException):
    pass


def inject_tags(schema, parent_tag="", injection_index=0, creative=True, **tags):
    """
    Injects a new tag with the specified content at the indicated parent and index
    :param schema: xml_string or xml.etree.ElementTree.Element where the tags are to be injected
    :param parent_tag: name of the parent tag where indicated tags are to be injected (leave blank for injecting to top level of schema)
    :param injection_index: indicates the index of where the tags will be inserted into their parents. 0 for first, 1 for second, so on
    :param tags: kwargs indicating tags and text of tags:
                 * thing="1" --->
                        <thing>1</thing>,
                 * provider={"text":"some text", "action":"info"} --->
                        <provider action="info">some text</provider>
                 * provider__1={"text":"some text", "action":"info"},
                   provider__2={"text":"other text", "action":"info"} --- >
                        <provider action="info">some text</provider>
                        <provider action="info">other text</provider>
    :return: modified xml_string with newly injected tags
    """
    # if the object is not an element, we treat it as an xml string
    if not isinstance(schema, ET.Element):
        schema = ET.fromstring(schema)
    # if no parent_tag is specified, the root is the parent
    if not parent_tag:
        parent = schema
    # if the specified parent_tag exists then that is our active parent
    elif schema.find(parent_tag) is not None:
        parent = schema.find(parent_tag)
    else:
        raise BadSchemaError(f"No <{parent_tag}/> tag included in the given schema.")
    for i, kword in enumerate(tags.keys()):
        # if creative then add a new tag on tag collision, if not creative then pass
        if parent.find(kword) is not None and not creative:
            pass
        else:
            if isinstance(tags[kword], dict):
                if '__inner_tag' in tags[kword].keys():
                    inner_tag = tags[kword].pop('__inner_tag')
                else:
                    inner_tag = ""
                if 'text' in tags[kword].keys() and not inner_tag:
                    text = tags[kword].pop('text')
                elif 'text' in tags[kword].keys():
                    raise BadTagError('Elements that contain elements may not also contain text'
                                              ' attributes (XML formatting does not allow it.)')
                else:
                    text = ""
                new_tag = ET.Element(kword.split('__')[0], tags[kword])

            elif isinstance(tags[kword], str):
                inner_tag = ""
                text = tags[kword]
                new_tag = ET.Element(kword.split('__')[0])
            else:
                raise TypeError(f"Passed kwarg '{kword} is {type(tags[kword])}. Must be str or dict.'")
            new_tag.text = text
            parent.insert(injection_index, new_tag)
            if inner_tag:
                inject_tags(new_tag, **inner_tag)
            injection_index += 1
    try:
        schema_str = ET.tostring(schema)
    except TypeError as e:
        raise TypeError(f"One of tags you attempted to inject is not a supported type: {e}")

    return schema_str


def _search_schema(schema_str, show_all=True, **kwarg):
    schema = XMLSchema(schema_str)
    paths = schema.locate(**kwarg)
    items = [schema.retrieve('__'.join(path.split('__')[:-1])) for path in paths]
    kwarg_key = list(kwarg.keys())[0].split('__')[0]
    try:
        sorted_list = sorted(items, key=lambda x: int(x[kwarg_key])) if show_all else \
            sorted(items, key=lambda x: int(x[kwarg_key]))[-1]
    except IndexError:  # happens when there are no results in the search
        sorted_list = None
    return sorted_list


def print_xml(schema_str):
    print(BeautifulSoup(schema_str, "xml").prettify())