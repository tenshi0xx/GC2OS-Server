import { Elysia } from "elysia"
import { xml } from "elysia-xml"
import { decrypt } from "../crypt/module"

interface AuthRequestBody {
    encrypted_payload: string;
}

type AuthQuery = {
    auth_token?: string;
}

export const gc2_auth = new Elysia() // wHY I NEED TO LET IT BLANK WTH it's feels wrong
    .group("/auth", (gc2_auth) => {
        .get("start.php", (Headers))
    })