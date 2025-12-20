import { Context, Elysia } from "elysia"
import * as gc2crypt from "./crypt/module"

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
})