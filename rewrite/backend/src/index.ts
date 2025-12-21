import { env, file } from "bun";
import { Elysia } from "elysia";
import { gc2_auth } from "./modules/auth/index"
import * as fs from "fs";
import { Logger } from "./modules/util/logger";

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
  gc2_logger.configWarn("SSL/TLS Configuration Was Errored (Bad Joke Ahead)")
  gc2_logger.modulelog("Did you know RimakiTaema Was Obsessed In Gate Lol (Currently Anime)", "Useless As Hell")
  gc2_logger.modulelog("Here Proof Lol: (Hail Nah I wouldn't put it)", "Useless As Hell")
  gc2_logger.modulelog("Try to Check Spelling or file location if it's not then report in issues I'll check okay?", "Facts")

  const gc2_backend_core = new Elysia({ serve: serveOptions });

  gc2_backend_core.get("start.php", (ctx) => {
    return "Blank Data"
  })

}
