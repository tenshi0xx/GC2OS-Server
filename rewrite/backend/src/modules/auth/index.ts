import { Context, Elysia } from "elysia"
import * as gc2crypt from "./crypt/module"
import { env } from "bun"

// const AES_TECHNOLOGY = Bun.env.AES_TECHNOLOGY!
const AES_ENCODING = Bun.env.AES_ENCODING as BufferEncoding

if (!Bun.env.AES_CBC_KEY)
    throw new Error("Missing AES_CBC_KEY, Did you set .env correctly?")
if (!Bun.env.AES_CBC_IV)
    throw new Error("Missing AES_CBC_IV, Did you set .env correctly?")

const AES_CBC_KEY = Buffer.from(Bun.env.AES_CBC_KEY!, AES_ENCODING!)
const AES_CBC_IV = Buffer.from(Bun.env.AES_CBC_IV)

function rawpayload(ctx: Context): string{
    const url = ctx.request.url
    const payload = url.indexOf("?")
    /* The Payload Getter Function */ 
    if (payload === -1)
        throw new Error("Payload Runtime Error (Unable to Get Payload Correctly")
    return url.slice(payload + 1)
}

export const gc2_auth = new Elysia() // wHY I NEED TO LET IT BLANK WTH it's feels wrong
gc2_auth.get('start.php', (ctx) => {
       const raw = rawpayload(ctx)
       const decrypted = gc2crypt.decryptAES(raw, AES_CBC_KEY, AES_CBC_IV)
       console.log(decrypted)
       /* I wana check Fields First Update Soon */
})