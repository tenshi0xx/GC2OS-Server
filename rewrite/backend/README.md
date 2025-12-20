# GC2OS-Server-BackendRuntime

## How to run
```bash
bun run src/index.ts
or
bun build \
	--compile \
	--minify-whitespace \
	--minify-syntax \
	--target bun \
	--outfile server \
	src/index.ts
after that run
./server (recommend for production and better speed afterall)
