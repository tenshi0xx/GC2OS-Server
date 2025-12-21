/*
*
* This helper was made with AI Sorry TT
*
*/


import { info } from "console";
import * as fs from "fs";
import * as path from "path";

class Logger {
  private logsDir: string;
  private configWarnLog: string;
  private engineerNotesLog: string;

  constructor() {
    this.logsDir = path.join(process.cwd(), "logs");
    this.configWarnLog = path.join(this.logsDir, "config-warnings.log");
    this.engineerNotesLog = path.join(this.logsDir, "engineer-notes.log");
    
    // Create logs directory if it doesn't exist
    if (!fs.existsSync(this.logsDir)) {
      fs.mkdirSync(this.logsDir, { recursive: true });
    }
  }

  private getTimestamp(): string {
    return new Date().toISOString().replace('T', ' ').substring(0, 19);
  }

  configWarn(message: string) {
    const logLine = `[${this.getTimestamp()}] [CONFIG WARN]: ${message}\n`;
    fs.appendFileSync(this.configWarnLog, logLine);
    console.warn(`[CONFIG WARN]: ${message}`);
  }

  engineerNote(message: string) {
    const logLine = `[${this.getTimestamp()}] [ENGINEER NOTE]: ${message}\n`;
    fs.appendFileSync(this.engineerNotesLog, logLine);
  }

  // Optional: General error logging
  error(message: string) {
    const timestamp = this.getTimestamp();
    console.error(`[${timestamp}] [ERROR]: ${message}`);
  }

  // Optional: Info logging
  info(message: string) {
    const timestamp = this.getTimestamp();
    console.log(`[${timestamp}] [INFO]: ${message}`);
  }
  // Optional: Module Logging
  modulelog(message: string, module_name: string) {
    const timestamp = this.getTimestamp()
    console.log(`[${timestamp}] [${module_name}]: ${message}`)
  }
}
export const logger = new Logger();
export { Logger };