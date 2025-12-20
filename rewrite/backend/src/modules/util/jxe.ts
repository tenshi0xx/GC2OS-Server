/*
*
* Now fixing some red okay it's was a type error (Sorry in Advance)
* - "Rimaki"
*/
import fs from "fs";
import path from "path";
import js2xmlparser from "js2xmlparser";

/**
 * Resolve JSON template path
 * @param {string} targetPath - directory OR file path
 * @param {string} name - template name (used only if targetPath is dir)
 */
function resolveTemplatePath(targetPath: string, name: string) {
    const resolved = path.resolve(targetPath);

    // If direct file path → use it
    if (fs.existsSync(resolved) && fs.statSync(resolved).isFile()) {
        return resolved;
    }

    // Otherwise treat as directory
    if (!name) {
        throw new Error("Template name required when using directory path");
    }

    return path.join(resolved, `${name}.json`);
}

/**
 * Load JSON template
 */
function loadTemplate(targetPath: string, name: string) {
    const file = resolveTemplatePath(targetPath, name);

    if (!fs.existsSync(file)) {
        throw new Error(`JXE template not found: ${file}`);
    }

    return JSON.parse(fs.readFileSync(file, "utf-8"));
}

/**
 * JSON → XML executor
 *
 * @param {string} targetPath - dir OR json file path
 * @param {string} name - template name (ignored if file path)
 * @param {object} data - dynamic data
 * @param {string} root - xml root name
 * @returns {string} XML string
 */
export function jxe(targetPath: string, name: string , data = {}, root = "response") {
    const template = loadTemplate(targetPath, name);

    if (template.data && typeof template.data === "object") {
        template.data = { ...template.data, ...data };
    }

    return js2xmlparser.parse(root, template);
}
