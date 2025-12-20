/*
*
* Coded with AI (Sorry in Advance)
* - "Rimaki"
*/

import fs from "fs";
import path from "path";
import js2xmlparser from "js2xmlparser";

export interface JXEData {
    [key: string]: any;
}

export interface JXETemplate {
    status: string;
    message: string;
    data?: JXEData;
}

const TEMPLATE_DIR = path.resolve('./templates');

export function loadTemplate(name: string): JXETemplate {
    const file = path.join(TEMPLATE_DIR, `${name}.json`);
    if (!fs.existsSync(file)) throw new Error(`Template ${name} not found`);
    return JSON.parse(fs.readFileSync(file, "utf-8")) as JXETemplate;
}

/**
 * Converts JSON template + optional data to XML
 * @param name - template name
 * @param data - optional dynamic data
 * @param rootName - XML root element name
 * @returns XML string
 */
export function jxe(name: string, data: JXEData = {}, rootName = "response"): string {
    const template = loadTemplate(name);
    if (template.data) template.data = { ...template.data, ...data };
    return js2xmlparser.parse(rootName, template);
}
