import { Context } from "elysia"

export function rawurldata(ctx: Context): string {
    try {
        const url = ctx.request.url
        const phpIndex = url.indexOf(".php?")

        if (phpIndex === -1)
            return ""

        return url.slice(phpIndex + 5)
    } catch (e) {
        return "";
    }
}