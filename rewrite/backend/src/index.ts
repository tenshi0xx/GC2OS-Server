import { env } from "bun";
import { Elysia } from "elysia";
import { gc2_auth } from "./modules/auth/index"
const port = Number(env.API_PORT ?? 3000);

const gc2 = new Elysia()
  .use(gc2_auth)
  .listen(port);

console.log(`🚀 API running on http://localhost:${port}`);