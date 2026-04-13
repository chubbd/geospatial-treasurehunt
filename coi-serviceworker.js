/* coi-serviceworker v0.1.7 - Guido Zuidhof, licensed under MIT
   https://github.com/gzuidhof/coi-serviceworker
   Injects Cross-Origin-Opener-Policy and Cross-Origin-Embedder-Policy headers
   so that SharedArrayBuffer (required by DuckDB-WASM pthreads) is available. */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) =>
  event.waitUntil(self.clients.claim())
);

async function handleFetch(request) {
  if (request.cache === "only-if-cached" && request.mode !== "same-origin") {
    return new Response("", {
      status: 504,
      statusText: "Gateway Timeout",
    });
  }

  let r;
  try {
    r = await fetch(request);
  } catch (e) {
    console.error(e);
    return new Response(e.toString(), {
      status: 502,
      statusText: "Bad Gateway",
    });
  }

  // Opaque responses (no-cors fetches) have status 0 and an unreadable body.
  // Trying to construct new Response(body, { status: 0 }) throws a RangeError
  // because status must be in [200, 599].  Pass them through unchanged; the
  // browser's COEP enforcement will deal with them separately.
  if (r.status === 0) {
    return r;
  }

  const newHeaders = new Headers(r.headers);
  newHeaders.set("Cross-Origin-Opener-Policy", "same-origin");
  newHeaders.set("Cross-Origin-Embedder-Policy", "require-corp");
  newHeaders.set("Cross-Origin-Resource-Policy", "cross-origin");

  return new Response(r.body, {
    status: r.status,
    statusText: r.statusText,
    headers: newHeaders,
  });
}

self.addEventListener("fetch", (event) => {
  event.respondWith(handleFetch(event.request));
});
