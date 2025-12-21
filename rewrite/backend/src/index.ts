import { env, file } from "bun";
import { Elysia } from "elysia";
import { gc2_auth } from "./modules/auth/index"
import * as fs from "fs";

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
    console.log("[HTTPS Technology]: TLS/SSL Enabled Successfully \n Serving In Domain Now Secure and possible")
  } else {
    throw new Error("[Critical] : HTTPS Technology Unable to load due to missing either key or cert please check in .env for correction \n fallback to http was made");
  }
} catch (err) {
  serveOptions: undefined;
  console.warn("[HTTPS Technology]: Due to Critical Error in TLS/SSL Disabling HTTPS (Bad Joke Ahead)")
  console.log("[Useless As Hell Joke]: Did you know RimakiTaema Was Obsessed In Gate Lol (Currently Anime)")

  const gc2_backend_core = new Elysia({ serve: serveOptions });

  gc2_backend_core.get("start.php", (ctx) => {
    return "Blank Data"
  })

}
