import { env, file } from "bun";
import { Elysia } from "elysia";
import { gc2_auth } from "./modules/auth/index"
import * as fs from "fs";
import { logger, Logger } from "./modules/util/logger";
import { rawurldata } from "./modules/util/url";

const gc2_logger = new Logger()

const port = Number(env.GC2_API_PORT ?? 3000);
const ip = (env.GC2_API_IP ?? "127.0.0.1");
const domain = (env.GC2_API_DOMAIN ?? "None")
const https_enabled = (env.GC2_API_HTTPS ?? false)
const cert_path = (env.GC2_API_CERT ?? "cert.pem")
const key_path = (env.GC2_API_KEY ?? "key.pem")
const hosti = domainchecker(domain)


function domainchecker(domain?: string): string{
  if (!domain || domain === "None") {
    return ip;
  }
  return domain;
}

let serveOptions;

try {
  if (fs.existsSync(cert_path) && fs.existsSync(key_path)) {
    serveOptions: {
      tls: {
        cert: file(cert_path)
        key: file(key_path)
      }
    };
    gc2_logger.modulelog("TLS/SSL Enabled Successfully, Now your Domain is Secure (Except Web proxy forgot it", "HTTPS Technology")
  } else {
    throw new Error("[Critical] : HTTPS Technology Unable to load due to missing either key or cert please check in .env for correction \n fallback to http was made");
  }
} catch (err) {
  serveOptions: undefined;
  /* The Jokes Was Nuked To prepare in prod mainstream repo (Not my repo)*/
  gc2_logger.configWarn("SSL/TLS Configuration Was Errored")
  gc2_logger.modulelog("Try to Check Spelling or file location", "gc2_auth")

  const gc2_backend_core = new Elysia({ serve: serveOptions });
  gc2_backend_core.group("*.php", (app) => {
    app.use(gc2_auth)
    return gc2_auth;
  });

  
  gc2_backend_core.listen({
    hostname: hosti,
    port: port
  })
  gc2_logger.modulelog(`GC2 Backend Is Online at ${https_enabled ? "https" : "http"}://${hosti}:${port}` , "Server Status")

}
