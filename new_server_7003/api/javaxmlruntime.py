import dicttoxml
import json

def jsontoxml(json_file_location):
    "Open Json file as what location feeds them"
    with open(json_file_location, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    "Converter Logic"

    xmlbyte = dicttoxml.convert(data)
    xmlstr = xmlbyte.decode()

    "Return Value to it wut?"
    return xmlstr