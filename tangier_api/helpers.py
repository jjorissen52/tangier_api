import xml.etree.ElementTree as ET


class BadSchemaError(BaseException):
    pass


class BadTagError(BaseException):
    pass


def _indent(elem, level=0):
    i = f"\n{level*'  '}"
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = f"{i} "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            _indent(elem, level + 2)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def pretty_print(schema_str, *keys):
    root = ET.fromstring(schema_str)
    tree = ET.ElementTree(root)
    _indent(root)
    item = root
    for key in keys:
        item = item[key]
    print(str(ET.tostring(item), 'utf-8'))