import { env } from "bun";
import { Elysia } from "elysia";

const port = Number(env.API_PORT ?? 3000);

const gc2 = new Elysia()
  .use(gc2_auth)
  .use(gc2_services)
  .listen(port);

console.log(`🚀 API running on http://localhost:${port}`);