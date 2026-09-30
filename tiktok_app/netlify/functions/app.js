// Shorts Media — TikTok Login Kit + Content Posting API, one Lambda-compat
// Netlify Function, self-contained (no npm install on deploy).
//
// Source of truth: tiktok_app/ in caleblschulte0-ux/Shorts-pipeline.
// Built into a deployable drop by scripts/build_tiktok_drop.py, which
// fills the __PLACEHOLDERS__ below from a local, never-committed config.
// Netlify env vars (TIKTOK_CLIENT_KEY, ...) win over the placeholders.
//
// Linked accounts live in Netlify Blobs; GitHub Actions on main fetch a
// fresh access token through /api/tiktok/token with an OIDC token
// (shared/uploaders.py:_tiktok_broker_token). The @netlify/blobs library is
// vendored below. A Lambda-compat function MUST call connectLambda(event)
// before any Blobs call and cannot do strong-consistency reads — the
// 2026-09 ChatGPT build did neither, so every account link failed.
"use strict";
var __getOwnPropNames = Object.getOwnPropertyNames;
var __commonJS = (cb, mod) => function __require() {
  return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
};

// builddeps/node_modules/@netlify/runtime-utils/dist/main.cjs
var require_main = __commonJS({
  "builddeps/node_modules/@netlify/runtime-utils/dist/main.cjs"(exports2, module2) {
    "use strict";
    var __defProp = Object.defineProperty;
    var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
    var __getOwnPropNames2 = Object.getOwnPropertyNames;
    var __hasOwnProp = Object.prototype.hasOwnProperty;
    var __export = (target, all) => {
      for (var name in all)
        __defProp(target, name, { get: all[name], enumerable: true });
    };
    var __copyProps = (to, from, except, desc) => {
      if (from && typeof from === "object" || typeof from === "function") {
        for (let key of __getOwnPropNames2(from))
          if (!__hasOwnProp.call(to, key) && key !== except)
            __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
      }
      return to;
    };
    var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);
    var main_exports = {};
    __export(main_exports, {
      base64Decode: () => base64Decode,
      base64Encode: () => base64Encode,
      getEnvironment: () => getEnvironment
    });
    module2.exports = __toCommonJS(main_exports);
    var getString = (input) => typeof input === "string" ? input : JSON.stringify(input);
    var base64Decode = globalThis.Buffer ? (input) => Buffer.from(input, "base64").toString() : (input) => atob(input);
    var base64Encode = globalThis.Buffer ? (input) => Buffer.from(getString(input)).toString("base64") : (input) => btoa(getString(input));
    var getEnvironment = () => {
      const { Deno, Netlify, process } = globalThis;
      return Netlify?.env ?? Deno?.env ?? {
        delete: (key) => delete process?.env[key],
        get: (key) => process?.env[key],
        has: (key) => Boolean(process?.env[key]),
        set: (key, value) => {
          if (process?.env) {
            process.env[key] = value;
          }
        },
        toObject: () => process?.env ?? {}
      };
    };
  }
});

// builddeps/node_modules/@netlify/otel/dist/main.cjs
var require_main2 = __commonJS({
  "builddeps/node_modules/@netlify/otel/dist/main.cjs"(exports2, module2) {
    "use strict";
    var __defProp = Object.defineProperty;
    var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
    var __getOwnPropNames2 = Object.getOwnPropertyNames;
    var __hasOwnProp = Object.prototype.hasOwnProperty;
    var __export = (target, all) => {
      for (var name in all)
        __defProp(target, name, { get: all[name], enumerable: true });
    };
    var __copyProps = (to, from, except, desc) => {
      if (from && typeof from === "object" || typeof from === "function") {
        for (let key of __getOwnPropNames2(from))
          if (!__hasOwnProp.call(to, key) && key !== except)
            __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
      }
      return to;
    };
    var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);
    var main_exports = {};
    __export(main_exports, {
      getTracer: () => getTracer,
      shutdownTracers: () => shutdownTracers,
      withActiveSpan: () => withActiveSpan
    });
    module2.exports = __toCommonJS(main_exports);
    var GET_TRACER = "__netlify__getTracer";
    var SHUTDOWN_TRACERS = "__netlify__shutdownTracers";
    var getTracer = (name, version) => {
      return globalThis[GET_TRACER]?.(name, version);
    };
    var shutdownTracers = async () => {
      return globalThis[SHUTDOWN_TRACERS]?.();
    };
    function withActiveSpan(tracer, name, optionsOrFn, contextOrFn, fn) {
      const func = typeof contextOrFn === "function" ? contextOrFn : typeof optionsOrFn === "function" ? optionsOrFn : fn;
      if (!func) {
        throw new Error("function to execute with active span is missing");
      }
      if (!tracer) {
        return func();
      }
      return tracer.withActiveSpan(name, optionsOrFn, contextOrFn, func);
    }
  }
});

// builddeps/node_modules/@netlify/blobs/dist/main.cjs
var require_main3 = __commonJS({
  "builddeps/node_modules/@netlify/blobs/dist/main.cjs"(exports2, module2) {
    "use strict";
    var __create = Object.create;
    var __defProp = Object.defineProperty;
    var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
    var __getOwnPropNames2 = Object.getOwnPropertyNames;
    var __getProtoOf = Object.getPrototypeOf;
    var __hasOwnProp = Object.prototype.hasOwnProperty;
    var __export = (target, all) => {
      for (var name in all)
        __defProp(target, name, { get: all[name], enumerable: true });
    };
    var __copyProps = (to, from, except, desc) => {
      if (from && typeof from === "object" || typeof from === "function") {
        for (let key of __getOwnPropNames2(from))
          if (!__hasOwnProp.call(to, key) && key !== except)
            __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
      }
      return to;
    };
    var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
      // If the importer is in node compatibility mode or this is not an ESM
      // file that has been converted to a CommonJS file using a Babel-
      // compatible transform (i.e. "__esModule" has not been set), then set
      // "default" to the CommonJS "module.exports" for node compatibility.
      isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
      mod
    ));
    var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);
    var main_exports = {};
    __export(main_exports, {
      connectLambda: () => connectLambda,
      getDeployStore: () => getDeployStore,
      getStore: () => getStore,
      listStores: () => listStores,
      setEnvironmentContext: () => setEnvironmentContext
    });
    module2.exports = __toCommonJS(main_exports);
    var import_runtime_utils = require_main();
    var getEnvironmentContext = () => {
      const context = globalThis.netlifyBlobsContext || (0, import_runtime_utils.getEnvironment)().get("NETLIFY_BLOBS_CONTEXT");
      if (typeof context !== "string" || !context) {
        return {};
      }
      const data = (0, import_runtime_utils.base64Decode)(context);
      try {
        return JSON.parse(data);
      } catch {
      }
      return {};
    };
    var setEnvironmentContext = (context) => {
      const encodedContext = (0, import_runtime_utils.base64Encode)(JSON.stringify(context));
      (0, import_runtime_utils.getEnvironment)().set("NETLIFY_BLOBS_CONTEXT", encodedContext);
    };
    var MissingBlobsEnvironmentError = class extends Error {
      constructor(requiredProperties) {
        super(
          `The environment has not been configured to use Netlify Blobs. To use it manually, supply the following properties when creating a store: ${requiredProperties.join(
            ", "
          )}`
        );
        this.name = "MissingBlobsEnvironmentError";
      }
    };
    var import_runtime_utils2 = require_main();
    var connectLambda = (event) => {
      const rawData = (0, import_runtime_utils2.base64Decode)(event.blobs);
      const data = JSON.parse(rawData);
      const environmentContext = {
        deployID: event.headers["x-nf-deploy-id"],
        edgeURL: data.url,
        siteID: event.headers["x-nf-site-id"],
        token: data.token
      };
      setEnvironmentContext(environmentContext);
    };
    var BlobsConsistencyError = class extends Error {
      constructor() {
        super(
          `Netlify Blobs has failed to perform a read using strong consistency because the environment has not been configured with a 'uncachedEdgeURL' property`
        );
        this.name = "BlobsConsistencyError";
      }
    };
    var import_runtime_utils3 = require_main();
    var BASE64_PREFIX = "b64;";
    var METADATA_HEADER_INTERNAL = "x-amz-meta-user";
    var METADATA_HEADER_EXTERNAL = "netlify-blobs-metadata";
    var METADATA_MAX_SIZE = 2 * 1024;
    var encodeMetadata = (metadata) => {
      if (!metadata) {
        return null;
      }
      const encodedObject = (0, import_runtime_utils3.base64Encode)(JSON.stringify(metadata));
      const payload = `b64;${encodedObject}`;
      if (METADATA_HEADER_EXTERNAL.length + payload.length > METADATA_MAX_SIZE) {
        throw new Error("Metadata object exceeds the maximum size");
      }
      return payload;
    };
    var decodeMetadata = (header) => {
      if (!header?.startsWith(BASE64_PREFIX)) {
        return {};
      }
      const encodedData = header.slice(BASE64_PREFIX.length);
      const decodedData = (0, import_runtime_utils3.base64Decode)(encodedData);
      const metadata = JSON.parse(decodedData);
      return metadata;
    };
    var getMetadataFromResponse = (response) => {
      if (!response.headers) {
        return {};
      }
      const value = response.headers.get(METADATA_HEADER_EXTERNAL) || response.headers.get(METADATA_HEADER_INTERNAL);
      try {
        return decodeMetadata(value);
      } catch {
        throw new Error(
          "An internal error occurred while trying to retrieve the metadata for an entry. Please try updating to the latest version of the Netlify Blobs client."
        );
      }
    };
    var REGION_AUTO = "auto";
    var regions = {
      "us-east-1": true,
      "us-east-2": true,
      "eu-central-1": true,
      "ap-southeast-1": true,
      "ap-southeast-2": true
    };
    var isValidRegion = (input) => Object.keys(regions).includes(input);
    var InvalidBlobsRegionError = class extends Error {
      constructor(region) {
        super(
          `${region} is not a supported Netlify Blobs region. Supported values are: ${Object.keys(regions).join(", ")}.`
        );
        this.name = "InvalidBlobsRegionError";
      }
    };
    var import_runtime_utils4 = require_main();
    var DEFAULT_RETRY_DELAY = (0, import_runtime_utils4.getEnvironment)().get("NODE_ENV") === "test" ? 1 : 5e3;
    var MIN_RETRY_DELAY = 1e3;
    var MAX_RETRY = 5;
    var RATE_LIMIT_HEADER = "X-RateLimit-Reset";
    var fetchAndRetry = async (fetch2, url, options, attemptsLeft = MAX_RETRY, getRetryUrl) => {
      try {
        const res = await fetch2(url, options);
        const isRetryable = res.status === 429 || res.status >= 500 || getRetryUrl !== void 0 && res.status === 403;
        if (attemptsLeft > 0 && isRetryable) {
          const delay = getDelay(res.headers.get(RATE_LIMIT_HEADER));
          await sleep(delay);
          const retryUrl = getRetryUrl ? await getRetryUrl() : url;
          return fetchAndRetry(fetch2, retryUrl, options, attemptsLeft - 1, getRetryUrl);
        }
        return res;
      } catch (error) {
        if (attemptsLeft === 0) {
          throw error;
        }
        const delay = getDelay();
        await sleep(delay);
        const retryUrl = getRetryUrl ? await getRetryUrl() : url;
        return fetchAndRetry(fetch2, retryUrl, options, attemptsLeft - 1, getRetryUrl);
      }
    };
    var getDelay = (rateLimitReset) => {
      if (!rateLimitReset) {
        return DEFAULT_RETRY_DELAY;
      }
      return Math.max(Number(rateLimitReset) * 1e3 - Date.now(), MIN_RETRY_DELAY);
    };
    var sleep = (ms) => new Promise((resolve) => {
      setTimeout(resolve, ms);
    });
    var import_node_process = __toESM(require("process"), 1);
    var import_otel = require_main2();
    var NF_ERROR = "x-nf-error";
    var NF_REQUEST_ID = "x-nf-request-id";
    var DEPLOY_STORE_PREFIX = "deploy:";
    var SITE_STORE_PREFIX = "site:";
    var isDeniedWrite = (res, { method, storeName }) => (res.status === 401 || res.status === 403) && (method === "put" || method === "delete") && storeName !== void 0 && !storeName.startsWith(DEPLOY_STORE_PREFIX);
    var blobsErrorMessage = (res, context, responseBody) => {
      let details = res.headers.get(NF_ERROR) || `${res.status} status code`;
      if (res.headers.has(NF_REQUEST_ID)) {
        details += `, ID: ${res.headers.get(NF_REQUEST_ID)}`;
      }
      if (isDeniedWrite(res, context)) {
        const storeName = context.storeName?.startsWith(SITE_STORE_PREFIX) ? context.storeName.slice(SITE_STORE_PREFIX.length) : context.storeName;
        return `Netlify Blobs could not write to store '${storeName}' (${details}). Builds and build plugins can only write to deploy-specific stores: use 'getDeployStore' instead of 'getStore', or pass a 'token' with write access to the store. If this code is not running in a build, check that the token and site ID are valid. See https://docs.netlify.com/build/data-and-storage/netlify-blobs/#deploy-specific-stores`;
      }
      let message = `Netlify Blobs has generated an internal error (${details})`;
      if (!res.headers.get(NF_ERROR) && responseBody) {
        message += `: ${responseBody}`;
      }
      return message;
    };
    var BlobsInternalError = class extends Error {
      constructor(res, context = {}, responseBody) {
        super(blobsErrorMessage(res, context, responseBody));
        this.name = "BlobsInternalError";
        this.status = res.status;
        this.responseBody = responseBody;
      }
    };
    var createBlobsInternalError = async (res, context = {}) => {
      const responseBody = await res.clone().text().catch(() => void 0);
      return new BlobsInternalError(res, context, responseBody);
    };
    var collectIterator = async (iterator) => {
      const result = [];
      for await (const item of iterator) {
        result.push(item);
      }
      return result;
    };
    function withSpan(span, name, fn) {
      if (span) return fn(span);
      return (0, import_otel.withActiveSpan)((0, import_otel.getTracer)(), name, (span2) => {
        return fn(span2);
      });
    }
    var SIGNED_URL_ACCEPT_HEADER = "application/json;type=signed-url";
    var Client = class {
      constructor({ apiURL, consistency, edgeURL, fetch: fetch2, region, siteID, token, uncachedEdgeURL }) {
        this.apiURL = apiURL;
        this.consistency = consistency ?? "eventual";
        this.edgeURL = edgeURL;
        this.fetch = fetch2 ?? globalThis.fetch;
        this.region = region;
        this.siteID = siteID;
        this.token = token;
        this.uncachedEdgeURL = uncachedEdgeURL;
        if (!this.fetch) {
          throw new Error(
            "Netlify Blobs could not find a `fetch` client in the global scope. You can either update your runtime to a version that includes `fetch` (like Node.js 18.0.0 or above), or you can supply your own implementation using the `fetch` property."
          );
        }
      }
      async getFinalRequest({
        consistency: opConsistency,
        key,
        metadata,
        method,
        parameters = {},
        storeName
      }) {
        const encodedMetadata = encodeMetadata(metadata);
        const consistency = opConsistency ?? this.consistency;
        let urlPath = `/${this.siteID}`;
        if (storeName) {
          urlPath += `/${storeName}`;
        }
        if (key) {
          urlPath += `/${key}`;
        }
        if (this.edgeURL) {
          if (consistency === "strong" && !this.uncachedEdgeURL) {
            throw new BlobsConsistencyError();
          }
          const headers = {
            authorization: `Bearer ${this.token}`
          };
          if (encodedMetadata) {
            headers[METADATA_HEADER_INTERNAL] = encodedMetadata;
          }
          if (this.region) {
            urlPath = `/region:${this.region}${urlPath}`;
          }
          const url2 = new URL(urlPath, consistency === "strong" ? this.uncachedEdgeURL : this.edgeURL);
          for (const key2 in parameters) {
            url2.searchParams.set(key2, parameters[key2]);
          }
          return {
            headers,
            url: url2.toString()
          };
        }
        const apiHeaders = { authorization: `Bearer ${this.token}` };
        const url = new URL(`/api/v1/blobs${urlPath}`, this.apiURL ?? "https://api.netlify.com");
        for (const key2 in parameters) {
          url.searchParams.set(key2, parameters[key2]);
        }
        if (this.region) {
          url.searchParams.set("region", this.region);
        }
        if (storeName === void 0 || key === void 0) {
          return {
            headers: apiHeaders,
            url: url.toString()
          };
        }
        if (encodedMetadata) {
          apiHeaders[METADATA_HEADER_EXTERNAL] = encodedMetadata;
        }
        if (method === "head" || method === "delete") {
          return {
            headers: apiHeaders,
            url: url.toString()
          };
        }
        const res = await this.fetch(url.toString(), {
          headers: { ...apiHeaders, accept: SIGNED_URL_ACCEPT_HEADER },
          method
        });
        if (res.status !== 200) {
          throw await createBlobsInternalError(res, { method, storeName });
        }
        const { url: signedURL } = await res.json();
        const userHeaders = encodedMetadata ? { [METADATA_HEADER_INTERNAL]: encodedMetadata } : void 0;
        return {
          headers: userHeaders,
          url: signedURL
        };
      }
      async makeRequest({
        body,
        conditions = {},
        consistency,
        headers: extraHeaders,
        key,
        metadata,
        method,
        parameters,
        storeName
      }) {
        const { headers: baseHeaders = {}, url } = await this.getFinalRequest({
          consistency,
          key,
          metadata,
          method,
          parameters,
          storeName
        });
        const headers = {
          ...baseHeaders,
          ...extraHeaders
        };
        if (method === "put") {
          headers["cache-control"] = "max-age=0, stale-while-revalidate=60";
        }
        if ("onlyIfMatch" in conditions && conditions.onlyIfMatch) {
          headers["if-match"] = conditions.onlyIfMatch;
        } else if ("onlyIfNew" in conditions && conditions.onlyIfNew) {
          headers["if-none-match"] = "*";
        }
        const options = {
          body,
          headers,
          method
        };
        if (body instanceof ReadableStream) {
          options.duplex = "half";
        }
        const usesSignedUrl = !this.edgeURL && key !== void 0 && storeName !== void 0 && method !== "head" && method !== "delete";
        let getRetryUrl;
        if (usesSignedUrl) {
          getRetryUrl = async () => {
            const finalRequest = await this.getFinalRequest({ consistency, key, metadata, method, parameters, storeName });
            return finalRequest.url;
          };
        }
        return fetchAndRetry(this.fetch, url, options, void 0, getRetryUrl);
      }
    };
    var getClientOptions = (options, contextOverride) => {
      const context = contextOverride ?? getEnvironmentContext();
      const siteID = context.siteID ?? options.siteID;
      const token = context.token ?? options.token;
      if (!siteID || !token) {
        throw new MissingBlobsEnvironmentError(["siteID", "token"]);
      }
      if (options.region !== void 0 && !isValidRegion(options.region)) {
        throw new InvalidBlobsRegionError(options.region);
      }
      const clientOptions = {
        apiURL: context.apiURL ?? options.apiURL,
        consistency: options.consistency,
        edgeURL: context.edgeURL ?? options.edgeURL,
        fetch: options.fetch,
        region: options.region,
        siteID,
        token,
        uncachedEdgeURL: context.uncachedEdgeURL ?? options.uncachedEdgeURL
      };
      return clientOptions;
    };
    var LEGACY_STORE_INTERNAL_PREFIX = "netlify-internal/legacy-namespace/";
    var STATUS_OK = 200;
    var STATUS_PRE_CONDITION_FAILED = 412;
    var Store = class _Store {
      constructor(options) {
        this.client = options.client;
        if ("deployID" in options) {
          _Store.validateDeployID(options.deployID);
          let name = DEPLOY_STORE_PREFIX + options.deployID;
          if (options.name) {
            name += `:${options.name}`;
          }
          this.name = name;
        } else if (options.name.startsWith(LEGACY_STORE_INTERNAL_PREFIX)) {
          const storeName = options.name.slice(LEGACY_STORE_INTERNAL_PREFIX.length);
          _Store.validateStoreName(storeName);
          this.name = storeName;
        } else {
          _Store.validateStoreName(options.name);
          this.name = SITE_STORE_PREFIX + options.name;
        }
      }
      async delete(key) {
        const res = await this.client.makeRequest({ key, method: "delete", storeName: this.name });
        if (![200, 204, 404].includes(res.status)) {
          throw new BlobsInternalError(res, { method: "delete", storeName: this.name });
        }
      }
      async deleteAll() {
        let totalDeletedBlobs = 0;
        let hasMore = true;
        while (hasMore) {
          const res = await this.client.makeRequest({ method: "delete", storeName: this.name });
          if (res.status !== 200) {
            throw new BlobsInternalError(res, { method: "delete", storeName: this.name });
          }
          const data = await res.json();
          if (typeof data.blobs_deleted !== "number") {
            throw new BlobsInternalError(res);
          }
          totalDeletedBlobs += data.blobs_deleted;
          hasMore = typeof data.has_more === "boolean" && data.has_more;
        }
        return {
          deletedBlobs: totalDeletedBlobs
        };
      }
      async get(key, options) {
        return withSpan(options?.span, "blobs.get", async (span) => {
          const { consistency, type } = options ?? {};
          span?.setAttributes({
            "blobs.store": this.name,
            "blobs.key": key,
            "blobs.type": type,
            "blobs.method": "GET",
            "blobs.consistency": consistency
          });
          const res = await this.client.makeRequest({
            consistency,
            key,
            method: "get",
            storeName: this.name
          });
          span?.setAttributes({
            "blobs.response.body.size": res.headers.get("content-length") ?? void 0,
            "blobs.response.status": res.status
          });
          if (res.status === 404) {
            return null;
          }
          if (res.status !== 200) {
            throw new BlobsInternalError(res);
          }
          if (type === void 0 || type === "text") {
            return res.text();
          }
          if (type === "arrayBuffer") {
            return res.arrayBuffer();
          }
          if (type === "blob") {
            return res.blob();
          }
          if (type === "json") {
            return res.json();
          }
          if (type === "stream") {
            return res.body;
          }
          throw new BlobsInternalError(res);
        });
      }
      async getMetadata(key, options = {}) {
        return withSpan(options?.span, "blobs.getMetadata", async (span) => {
          span?.setAttributes({
            "blobs.store": this.name,
            "blobs.key": key,
            "blobs.method": "HEAD",
            "blobs.consistency": options.consistency
          });
          const res = await this.client.makeRequest({
            consistency: options.consistency,
            key,
            method: "head",
            storeName: this.name
          });
          span?.setAttributes({
            "blobs.response.status": res.status
          });
          if (res.status === 404) {
            return null;
          }
          if (res.status !== 200 && res.status !== 304) {
            throw new BlobsInternalError(res);
          }
          const etag = res?.headers.get("etag") ?? void 0;
          const metadata = getMetadataFromResponse(res);
          const result = {
            etag,
            metadata
          };
          return result;
        });
      }
      async getWithMetadata(key, options) {
        return withSpan(options?.span, "blobs.getWithMetadata", async (span) => {
          const { consistency, etag: requestETag, type } = options ?? {};
          const headers = requestETag ? { "if-none-match": requestETag } : void 0;
          span?.setAttributes({
            "blobs.store": this.name,
            "blobs.key": key,
            "blobs.method": "GET",
            "blobs.consistency": options?.consistency,
            "blobs.type": type,
            "blobs.request.etag": requestETag
          });
          const res = await this.client.makeRequest({
            consistency,
            headers,
            key,
            method: "get",
            storeName: this.name
          });
          const responseETag = res?.headers.get("etag") ?? void 0;
          span?.setAttributes({
            "blobs.response.body.size": res.headers.get("content-length") ?? void 0,
            "blobs.response.etag": responseETag,
            "blobs.response.status": res.status
          });
          if (res.status === 404) {
            return null;
          }
          if (res.status !== 200 && res.status !== 304) {
            throw new BlobsInternalError(res);
          }
          const metadata = getMetadataFromResponse(res);
          const result = {
            etag: responseETag,
            metadata
          };
          if (res.status === 304 && requestETag) {
            return { data: null, ...result };
          }
          if (type === void 0 || type === "text") {
            return { data: await res.text(), ...result };
          }
          if (type === "arrayBuffer") {
            return { data: await res.arrayBuffer(), ...result };
          }
          if (type === "blob") {
            return { data: await res.blob(), ...result };
          }
          if (type === "json") {
            return { data: await res.json(), ...result };
          }
          if (type === "stream") {
            return { data: res.body, ...result };
          }
          throw new Error(`Invalid 'type' property: ${type}. Expected: arrayBuffer, blob, json, stream, or text.`);
        });
      }
      list(options = {}) {
        return withSpan(options.span, "blobs.list", (span) => {
          span?.setAttributes({
            "blobs.store": this.name,
            "blobs.method": "GET",
            "blobs.list.paginate": options.paginate ?? false
          });
          const iterator = this.getListIterator(options);
          if (options.paginate) {
            return iterator;
          }
          return collectIterator(iterator).then(
            (items) => items.reduce(
              (acc, item) => ({
                blobs: [...acc.blobs, ...item.blobs],
                directories: [...acc.directories, ...item.directories]
              }),
              { blobs: [], directories: [] }
            )
          );
        });
      }
      async set(key, data, options = {}) {
        return withSpan(options.span, "blobs.set", async (span) => {
          span?.setAttributes({
            "blobs.store": this.name,
            "blobs.key": key,
            "blobs.method": "PUT",
            "blobs.data.size": typeof data == "string" ? data.length : data instanceof Blob ? data.size : data.byteLength,
            "blobs.data.type": typeof data == "string" ? "string" : data instanceof Blob ? "blob" : "arrayBuffer",
            "blobs.atomic": Boolean(options.onlyIfMatch ?? options.onlyIfNew)
          });
          _Store.validateKey(key);
          const conditions = _Store.getConditions(options);
          const res = await this.client.makeRequest({
            conditions,
            body: data,
            key,
            metadata: options.metadata,
            method: "put",
            storeName: this.name
          });
          const etag = res.headers.get("etag") ?? "";
          span?.setAttributes({
            "blobs.response.etag": etag,
            "blobs.response.status": res.status
          });
          if (conditions) {
            return res.status === STATUS_PRE_CONDITION_FAILED ? { modified: false } : { etag, modified: true };
          }
          if (res.status === STATUS_OK) {
            return {
              etag,
              modified: true
            };
          }
          throw await createBlobsInternalError(res, { method: "put", storeName: this.name });
        });
      }
      async setJSON(key, data, options = {}) {
        return withSpan(options.span, "blobs.setJSON", async (span) => {
          span?.setAttributes({
            "blobs.store": this.name,
            "blobs.key": key,
            "blobs.method": "PUT",
            "blobs.data.type": "json",
            "blobs.atomic": Boolean(options.onlyIfMatch ?? options.onlyIfNew)
          });
          _Store.validateKey(key);
          const conditions = _Store.getConditions(options);
          const payload = JSON.stringify(data);
          const headers = {
            "content-type": "application/json"
          };
          const res = await this.client.makeRequest({
            conditions,
            body: payload,
            headers,
            key,
            metadata: options.metadata,
            method: "put",
            storeName: this.name
          });
          const etag = res.headers.get("etag") ?? "";
          span?.setAttributes({
            "blobs.response.etag": etag,
            "blobs.response.status": res.status
          });
          if (conditions) {
            return res.status === STATUS_PRE_CONDITION_FAILED ? { modified: false } : { etag, modified: true };
          }
          if (res.status === STATUS_OK) {
            return {
              etag,
              modified: true
            };
          }
          throw new BlobsInternalError(res, { method: "put", storeName: this.name });
        });
      }
      static formatListResultBlob(result) {
        if (!result.key) {
          return null;
        }
        return {
          etag: result.etag,
          key: result.key
        };
      }
      static getConditions(options) {
        if ("onlyIfMatch" in options && "onlyIfNew" in options) {
          throw new Error(
            `The 'onlyIfMatch' and 'onlyIfNew' options are mutually exclusive. Using 'onlyIfMatch' will make the write succeed only if there is an entry for the key with the given content, while 'onlyIfNew' will make the write succeed only if there is no entry for the key.`
          );
        }
        if ("onlyIfMatch" in options && options.onlyIfMatch) {
          if (typeof options.onlyIfMatch !== "string") {
            throw new Error(`The 'onlyIfMatch' property expects a string representing an ETag.`);
          }
          return {
            onlyIfMatch: options.onlyIfMatch
          };
        }
        if ("onlyIfNew" in options && options.onlyIfNew) {
          if (typeof options.onlyIfNew !== "boolean") {
            throw new Error(
              `The 'onlyIfNew' property expects a boolean indicating whether the write should fail if an entry for the key already exists.`
            );
          }
          return {
            onlyIfNew: true
          };
        }
      }
      static validateKey(key) {
        if (key === "") {
          throw new Error("Blob key must not be empty.");
        }
        if (key.startsWith("/") || key.startsWith("%2F")) {
          throw new Error("Blob key must not start with forward slash (/).");
        }
        if (new TextEncoder().encode(key).length > 600) {
          throw new Error(
            "Blob key must be a sequence of Unicode characters whose UTF-8 encoding is at most 600 bytes long."
          );
        }
      }
      static validateDeployID(deployID) {
        if (!/^\w{1,24}$/.test(deployID)) {
          throw new Error(`'${deployID}' is not a valid Netlify deploy ID.`);
        }
      }
      static validateStoreName(name) {
        if (name.includes("/") || name.includes("%2F")) {
          throw new Error("Store name must not contain forward slashes (/).");
        }
        if (new TextEncoder().encode(name).length > 64) {
          throw new Error(
            "Store name must be a sequence of Unicode characters whose UTF-8 encoding is at most 64 bytes long."
          );
        }
      }
      getListIterator(options) {
        const { client, name: storeName } = this;
        const parameters = {};
        if (options?.prefix) {
          parameters.prefix = options.prefix;
        }
        if (options?.directories) {
          parameters.directories = "true";
        }
        return {
          [Symbol.asyncIterator]() {
            let currentCursor = null;
            let done = false;
            return {
              async next() {
                return withSpan(options?.span, "blobs.list.next", async (span) => {
                  span?.setAttributes({
                    "blobs.store": storeName,
                    "blobs.method": "GET",
                    "blobs.list.paginate": options?.paginate ?? false,
                    "blobs.list.done": done,
                    "blobs.list.cursor": currentCursor ?? void 0
                  });
                  if (done) {
                    return { done: true, value: void 0 };
                  }
                  const nextParameters = { ...parameters };
                  if (currentCursor !== null) {
                    nextParameters.cursor = currentCursor;
                  }
                  const res = await client.makeRequest({
                    method: "get",
                    parameters: nextParameters,
                    storeName
                  });
                  span?.setAttributes({
                    "blobs.response.status": res.status
                  });
                  let blobs = [];
                  let directories = [];
                  if (![200, 204, 404].includes(res.status)) {
                    throw new BlobsInternalError(res);
                  }
                  if (res.status === 404) {
                    done = true;
                  } else {
                    const page2 = await res.json();
                    if (page2.next_cursor) {
                      currentCursor = page2.next_cursor;
                    } else {
                      done = true;
                    }
                    blobs = (page2.blobs ?? []).map(_Store.formatListResultBlob).filter(Boolean);
                    directories = page2.directories ?? [];
                  }
                  return {
                    done: false,
                    value: {
                      blobs,
                      directories
                    }
                  };
                });
              }
            };
          }
        };
      }
    };
    var getDeployStoreRegion = (clientOptions, context) => {
      if (clientOptions.region) {
        return clientOptions.region;
      }
      if (clientOptions.edgeURL || clientOptions.uncachedEdgeURL) {
        if (!context.primaryRegion) {
          throw new Error(
            "When accessing a deploy store, the Netlify Blobs client needs to be configured with a region, and one was not found in the environment. To manually set the region, set the `region` property in the store options. If you are using the Netlify CLI, you may have an outdated version; run `npm install -g netlify-cli@latest` to update and try again."
          );
        }
        return context.primaryRegion;
      }
      return REGION_AUTO;
    };
    var getDeployStore = (input = {}, options) => {
      const context = getEnvironmentContext();
      const mergedOptions = typeof input === "string" ? { ...options, name: input } : input;
      const deployID = mergedOptions.deployID ?? context.deployID;
      if (!deployID) {
        throw new MissingBlobsEnvironmentError(["deployID"]);
      }
      const clientOptions = getClientOptions(mergedOptions, context);
      clientOptions.region = getDeployStoreRegion(clientOptions, context);
      const client = new Client(clientOptions);
      return new Store({ client, deployID, name: mergedOptions.name });
    };
    var getStore = (input, options) => {
      if (typeof input === "string") {
        const contextOverride = options?.siteID && options?.token ? { siteID: options?.siteID, token: options?.token } : void 0;
        const clientOptions = getClientOptions(options ?? {}, contextOverride);
        const client = new Client(clientOptions);
        return new Store({ client, name: input });
      }
      if (typeof input?.name === "string") {
        const { name } = input;
        const contextOverride = input?.siteID && input?.token ? { siteID: input?.siteID, token: input?.token } : void 0;
        const clientOptions = getClientOptions(input, contextOverride);
        if (!name) {
          throw new MissingBlobsEnvironmentError(["name"]);
        }
        const client = new Client(clientOptions);
        return new Store({ client, name });
      }
      if (typeof input?.deployID === "string") {
        const context = getEnvironmentContext();
        const clientOptions = getClientOptions(input, context);
        const { deployID } = input;
        if (!deployID) {
          throw new MissingBlobsEnvironmentError(["deployID"]);
        }
        clientOptions.region = getDeployStoreRegion(clientOptions, context);
        const client = new Client(clientOptions);
        return new Store({ client, deployID });
      }
      throw new Error(
        "The `getStore` method requires the name of the store as a string or as the `name` property of an options object"
      );
    };
    function listStores(options = {}) {
      const context = getEnvironmentContext();
      const clientOptions = getClientOptions(options, context);
      const client = new Client(clientOptions);
      const iterator = getListIterator(client, SITE_STORE_PREFIX);
      if (options.paginate) {
        return iterator;
      }
      return collectIterator(iterator).then((results) => ({ stores: results.flatMap((page2) => page2.stores) }));
    }
    var formatListStoreResponse = (stores) => stores.filter((store) => !store.startsWith(DEPLOY_STORE_PREFIX)).map((store) => store.startsWith(SITE_STORE_PREFIX) ? store.slice(SITE_STORE_PREFIX.length) : store);
    var getListIterator = (client, prefix) => {
      const parameters = {
        prefix
      };
      return {
        [Symbol.asyncIterator]() {
          let currentCursor = null;
          let done = false;
          return {
            async next() {
              if (done) {
                return { done: true, value: void 0 };
              }
              const nextParameters = { ...parameters };
              if (currentCursor !== null) {
                nextParameters.cursor = currentCursor;
              }
              const res = await client.makeRequest({
                method: "get",
                parameters: nextParameters
              });
              if (res.status === 404) {
                return { done: true, value: void 0 };
              }
              const page2 = await res.json();
              if (page2.next_cursor) {
                currentCursor = page2.next_cursor;
              } else {
                done = true;
              }
              return {
                done: false,
                value: {
                  ...page2,
                  stores: formatListStoreResponse(page2.stores)
                }
              };
            }
          };
        }
      };
    };
  }
});

// livev2/netlify/functions/account_service.js
var require_account_service = __commonJS({
  "livev2/netlify/functions/account_service.js"(exports2, module2) {
    "use strict";
    var crypto2 = require("node:crypto");
    var { getStore, connectLambda } = require_main3();
    function connect(event) {
      if (!event || !event.blobs) throw new Error("Netlify Blobs is not available to this function (event.blobs missing) — deploy through Netlify's build (CLI or Git), not a static-only upload");
      connectLambda(event);
    }
    var SITE2 = "https://shorts-media.netlify.app";
    var AUDIENCE = SITE2 + "/api/tiktok/token";
    var REPOSITORY_ID = "1251576094";
    var ISSUER = "https://token.actions.githubusercontent.com";
    var STORE_NAME = "shorts-media-tiktok-accounts";
    var TT_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/";
    function store() {
      return getStore({ name: STORE_NAME });
    }
    function keyFor(openId) {
      return "accounts/" + crypto2.createHash("sha256").update(String(openId)).digest("hex");
    }
    function safeHandle(value) {
      return String(value || "").replace(/^@/, "").trim().toLowerCase();
    }
    function recordFromToken(tok, details, previous) {
      if (!tok.open_id || !tok.access_token || !tok.refresh_token) throw new Error("TikTok did not provide persistent authorization");
      const now = Date.now();
      return {
        open_id: tok.open_id,
        handle: safeHandle(details.handle || previous && previous.handle),
        name: details.name || previous && previous.name || "TikTok user",
        avatar: details.avatar || previous && previous.avatar || "/app-assets/img/avatar.svg",
        access_token: tok.access_token,
        refresh_token: tok.refresh_token,
        access_expires_at: now + 1e3 * Number(tok.expires_in || 86400),
        refresh_expires_at: now + 1e3 * Number(tok.refresh_expires_in || 31536e3),
        scopes: tok.scope || previous && previous.scopes || "",
        connected_at: previous && previous.connected_at || now
      };
    }
    async function saveAuthorization(tok, details) {
      const db = store();
      const key = keyFor(tok.open_id);
      const previous = await db.get(key, { type: "json" });
      const record = recordFromToken(tok, details, previous);
      await db.setJSON(key, record);
      return record;
    }
    async function getRecord(openId) {
      return store().get(keyFor(openId), { type: "json" });
    }
    async function removeRecord(openId) {
      return store().delete(keyFor(openId));
    }
    async function listRecords() {
      const db = store();
      let cursor;
      const records = [];
      do {
        const page2 = await db.list({ prefix: "accounts/", cursor });
        for (const item of page2.blobs) {
          const rec = await db.get(item.key, { type: "json" });
          if (rec) records.push(rec);
        }
        cursor = page2.cursor;
      } while (cursor);
      return records;
    }
    async function refreshRecord(openId, config) {
      const db = store();
      const key = keyFor(openId);
      let existing = await db.getWithMetadata(key, { type: "json" });
      if (!existing) throw new Error("TikTok account is not saved yet (a new connection can take up to a minute to appear) or was disconnected");
      let rec = existing.data;
      if (rec.access_expires_at > Date.now() + 60 * 60 * 1e3) return rec;
      if (rec.refresh_expires_at < Date.now()) throw new Error("TikTok authorization expired; reconnect the account");
      const res = await fetch(TT_TOKEN_URL, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          client_key: config.client_key,
          client_secret: config.client_secret,
          grant_type: "refresh_token",
          refresh_token: rec.refresh_token
        })
      });
      const tok = await res.json();
      if (!res.ok || !tok.access_token || !tok.refresh_token || tok.open_id !== openId) {
        const newer = await db.getWithMetadata(key, { type: "json" });
        if (newer && newer.etag !== existing.etag && newer.data.access_expires_at > Date.now()) return newer.data;
        throw new Error("TikTok token refresh failed; reconnect the account");
      }
      const updated = recordFromToken(tok, rec, rec);
      const write = await db.setJSON(key, updated, { onlyIfMatch: existing.etag });
      if (write.modified) return updated;
      existing = await db.getWithMetadata(key, { type: "json" });
      if (existing && existing.data.access_expires_at > Date.now()) return existing.data;
      throw new Error("Concurrent token refresh did not complete");
    }
    function decodePart(value) {
      return JSON.parse(Buffer.from(value, "base64url").toString("utf8"));
    }
    async function verifyGithubOidc(event) {
      const authorization = event.headers.authorization || event.headers.Authorization || "";
      if (!authorization.startsWith("Bearer ")) return false;
      const jwt = authorization.slice(7);
      if (jwt.length > 12e3) return false;
      const parts = jwt.split(".");
      if (parts.length !== 3) return false;
      let header, claims;
      try {
        header = decodePart(parts[0]);
        claims = decodePart(parts[1]);
      } catch {
        return false;
      }
      const now = Math.floor(Date.now() / 1e3);
      if (header.alg !== "RS256" || !header.kid || claims.iss !== ISSUER || claims.aud !== AUDIENCE || String(claims.repository_id) !== REPOSITORY_ID || claims.repository !== "caleblschulte0-ux/Shorts-pipeline" || claims.ref !== "refs/heads/main" || claims.event_name === "pull_request" || !Number.isFinite(claims.iat) || !Number.isFinite(claims.exp) || claims.iat > now + 60 || claims.exp <= now || claims.exp > now + 3600) return false;
      const response = await fetch(ISSUER + "/.well-known/jwks");
      if (!response.ok) return false;
      const jwks = await response.json();
      const jwk = (jwks.keys || []).find((key) => key.kid === header.kid && key.kty === "RSA" && key.use === "sig");
      if (!jwk) return false;
      try {
        return crypto2.verify(
          "RSA-SHA256",
          Buffer.from(parts[0] + "." + parts[1]),
          crypto2.createPublicKey({ key: jwk, format: "jwk" }),
          Buffer.from(parts[2], "base64url")
        );
      } catch {
        return false;
      }
    }
    module2.exports = {
      AUDIENCE,
      connect,
      getRecord,
      keyFor,
      listRecords,
      refreshRecord,
      removeRecord,
      safeHandle,
      saveAuthorization,
      verifyGithubOidc
    };
  }
});

// livev2/netlify/functions/app.js
var crypto = require("crypto");
var accounts = require_account_service();
var blobs = require_main3();
// A build with --config fills the __MARKERS__; a build with --placeholders
// leaves them, and the site's Netlify environment supplies the values. Only
// TIKTOK_CLIENT_SECRET is truly required: the client key is public (it is in
// every consent URL) and the cookie-signing key is derived from the secret
// when none is set.
var unfilled = (mark, fallback) => /^__[A-Z_]+__$/.test(mark) ? fallback : mark;
var CONFIG = {
  client_key: process.env.TIKTOK_CLIENT_KEY || unfilled("__TIKTOK_CLIENT_KEY__", "aw9hmk3x2xmhv4mv"),
  client_secret: process.env.TIKTOK_CLIENT_SECRET || "__TIKTOK_CLIENT_SECRET__",
  redirect_uri: process.env.TIKTOK_REDIRECT_URI || "https://shorts-media.netlify.app/auth/tiktok/callback/",
  cookie_secret: process.env.SM_COOKIE_SECRET || unfilled("__SM_COOKIE_SECRET__", "")
};
if (!CONFIG.cookie_secret) CONFIG.cookie_secret = crypto.createHash("sha256").update("shorts-media-cookie:" + CONFIG.client_secret).digest("hex");
var SITE = "https://shorts-media.netlify.app";
var TT = "https://open.tiktokapis.com";
var GITHUB_API = "https://api.github.com";
var SCOPES = "user.info.basic,video.upload,video.publish";
// Every user's library (the sources they added and the videos found in
// them) lives in Netlify Blobs, one record per TikTok account.
var LIB_STORE = "shorts-media-libraries";
var MAX_SOURCES = 12;
var MAX_VIDEOS = 200;
// TikTok's FILE_UPLOAD takes a video in chunks of 5-64 MB; each chunk is
// moved by one function invocation (a page refresh drives the next one),
// so a video of any size fits inside Netlify's per-request limits.
var CHUNK = 5 * 1024 * 1024;
var MAX_VIDEO_BYTES = 500 * 1024 * 1024;
var VIDEO_EXT = /\.(mp4|mov|webm)(\?.*)?$/i;
// The one video every library can add in a click, so a new user (or a
// reviewer) can try the whole flow before adding their own sources.
var SAMPLE = {
  id: "sample-urban-growth",
  title: "Urban Growth Just Hit A 50-Year Low Of 1.36%",
  caption: "Everyone assumes cities are exploding faster than ever — but the world's urban growth rate just fell to its slowest pace in over 50 years.\n\n#data #cities #urbanization #explained",
  length: "1:36",
  url: SITE + "/app-assets/media/urban-growth.mp4",
  poster: "/app-assets/media/urban-growth-poster.png",
  size: 4460954,
  kind: "sample"
};
var esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;" })[c]);
function sign(payload) {
  const body = Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
  const mac = crypto.createHmac("sha256", CONFIG.cookie_secret).update(body).digest("base64url");
  return body + "." + mac;
}
function verify(value) {
  if (!value || value.indexOf(".") < 0) return null;
  const [body, mac] = value.split(".");
  const want = crypto.createHmac("sha256", CONFIG.cookie_secret).update(body).digest("base64url");
  if (mac.length !== want.length || !crypto.timingSafeEqual(Buffer.from(mac), Buffer.from(want))) return null;
  try {
    return JSON.parse(Buffer.from(body, "base64url").toString("utf8"));
  } catch {
    return null;
  }
}
function cookies(event) {
  const out = {};
  for (const part of String(event.headers.cookie || event.headers.Cookie || "").split(";")) {
    const i = part.indexOf("=");
    if (i > 0) out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}
function setCookie(name, value, maxAge) {
  return `${name}=${encodeURIComponent(value)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`;
}
var BASE_HEADERS = {
  "Content-Type": "text/html; charset=utf-8",
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  // media-src https: — previews play straight from GitHub's release CDN
  // (or wherever the user's direct link points). No script runs here.
  "Content-Security-Policy": "default-src 'self'; img-src 'self' data: https:; media-src 'self' https:; style-src 'self' 'unsafe-inline'; script-src 'none'; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
};
function jsonPage(statusCode, data) {
  return { statusCode, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" }, body: JSON.stringify(data) };
}
function page(body, extra) {
  return { statusCode: 200, headers: Object.assign({}, BASE_HEADERS, extra || {}), body };
}
function redirect(to, extra) {
  const where = /^https?:/.test(to) ? to : SITE + to;
  return { statusCode: 302, headers: Object.assign({ Location: where, "Cache-Control": "no-store" }, extra || {}), body: "" };
}
async function tt(path, token, body, method) {
  const res = await fetch(TT + path, {
    method: method || "POST",
    headers: { Authorization: "Bearer " + token, "Content-Type": "application/json; charset=UTF-8" },
    body: body === void 0 ? void 0 : JSON.stringify(body)
  });
  const json = await res.json().catch(() => ({}));
  const err = json.error || {};
  if (err.code && err.code !== "ok") throw new Error(`${err.code}: ${err.message || ""} (${err.log_id || ""})`);
  return json.data || {};
}
function form(event) {
  const raw = event.isBase64Encoded ? Buffer.from(event.body || "", "base64").toString("utf8") : event.body || "";
  const out = {};
  for (const [k, v] of new URLSearchParams(raw)) out[k] = v;
  return out;
}

// ---------- the library: sources and the videos found in them ----------
function libStore() {
  return blobs.getStore({ name: LIB_STORE });
}
function libKey(openId) {
  return "libraries/" + crypto.createHash("sha256").update(String(openId)).digest("hex");
}
function emptyLibrary() {
  return { v: 1, sources: [], videos: [], updated: 0 };
}
async function loadLibrary(openId) {
  const got = await libStore().getWithMetadata(libKey(openId), { type: "json" });
  if (!got || !got.data) return { lib: emptyLibrary(), etag: null };
  const lib = Object.assign(emptyLibrary(), got.data);
  lib.sources = Array.isArray(lib.sources) ? lib.sources : [];
  lib.videos = Array.isArray(lib.videos) ? lib.videos : [];
  return { lib, etag: got.etag || null };
}
async function saveLibrary(openId, lib, etag) {
  lib.updated = Date.now();
  const db = libStore();
  const key = libKey(openId);
  const options = etag ? { onlyIfMatch: etag } : { onlyIfNew: true };
  const write = await db.setJSON(key, lib, options);
  if (write.modified) return lib;
  // Someone else (another tab) wrote first: merge onto the newest copy.
  const newest = await db.getWithMetadata(key, { type: "json" });
  const base = Object.assign(emptyLibrary(), newest && newest.data || {});
  const merged = mergeLibraries(base, lib);
  merged.updated = Date.now();
  await db.setJSON(key, merged, newest ? { onlyIfMatch: newest.etag } : {});
  return merged;
}
function mergeLibraries(base, mine) {
  const out = emptyLibrary();
  const seenS = new Set(); const seenV = new Set();
  for (const s of [...mine.sources, ...base.sources]) if (!seenS.has(s.id)) { seenS.add(s.id); out.sources.push(s); }
  for (const v of [...mine.videos, ...base.videos]) if (!seenV.has(v.id) && seenS.has(v.source)) { seenV.add(v.id); out.videos.push(v); }
  return out;
}
function videoId(url) {
  return "v" + crypto.createHash("sha256").update(String(url)).digest("hex").slice(0, 16);
}
function sourceId(kind, ref) {
  return kind + ":" + crypto.createHash("sha256").update(kind + "\n" + String(ref).toLowerCase()).digest("hex").slice(0, 12);
}
function niceTitle(name) {
  const t = String(name || "").replace(VIDEO_EXT, "").replace(/[-_]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 100);
  return t ? t[0].toUpperCase() + t.slice(1) : "Untitled video";
}
function repoFrom(text) {
  let s = String(text || "").trim();
  s = s.replace(/^https?:\/\/(www\.)?github\.com\//i, "").replace(/\.git$/i, "").replace(/\/+$/, "");
  const m = s.match(/^([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))\/([A-Za-z0-9._-]{1,100})(?:\/.*)?$/);
  return m ? m[1] + "/" + m[2] : "";
}
function githubHeaders() {
  const h = { Accept: "application/vnd.github+json", "User-Agent": "Shorts-Media/1.0 (+https://shorts-media.netlify.app)", "X-GitHub-Api-Version": "2022-11-28" };
  if (process.env.GITHUB_TOKEN) h.Authorization = "Bearer " + process.env.GITHUB_TOKEN;
  return h;
}
// The videos published as release assets of a public GitHub repository:
// every .mp4/.mov/.webm attached to any release, newest first.
async function githubVideos(repo, sid) {
  const res = await fetch(`${GITHUB_API}/repos/${repo}/releases?per_page=30`, { headers: githubHeaders() });
  if (res.status === 404) throw new Error(`GitHub has no public repository called ${repo}.`);
  if (res.status === 403 || res.status === 429) throw new Error("GitHub is rate-limiting requests right now. Try again in a few minutes.");
  if (!res.ok) throw new Error(`GitHub answered ${res.status}.`);
  const releases = await res.json();
  if (!Array.isArray(releases)) throw new Error("GitHub sent an unexpected answer.");
  const out = [];
  for (const rel of releases) {
    if (rel.draft) continue;
    const assets = (rel.assets || []).filter((a) => a && VIDEO_EXT.test(a.name || "") && a.browser_download_url);
    for (const a of assets) {
      const size = Number(a.size || 0);
      out.push({
        id: videoId(a.browser_download_url),
        title: assets.length === 1 && rel.name ? String(rel.name).slice(0, 100) : niceTitle(a.name),
        caption: assets.length === 1 && rel.body ? String(rel.body).slice(0, 2200) : "",
        url: a.browser_download_url,
        size,
        kind: "github",
        source: sid,
        release: rel.tag_name || "",
        when: a.updated_at || rel.published_at || "",
        tooBig: size > MAX_VIDEO_BYTES
      });
    }
  }
  return out;
}
async function linkVideo(url, sid) {
  let u;
  try {
    u = new URL(String(url || "").trim());
  } catch {
    throw new Error("That is not a web address.");
  }
  if (u.protocol !== "https:") throw new Error("The link must start with https://.");
  const res = await fetch(u.toString(), { method: "HEAD", redirect: "follow" });
  if (!res.ok) throw new Error(`That link answered ${res.status}.`);
  const type = String(res.headers.get("content-type") || "").toLowerCase();
  if (!type.startsWith("video/") && !VIDEO_EXT.test(u.pathname)) throw new Error("That link is not a video file (mp4, mov or webm).");
  const size = Number(res.headers.get("content-length") || 0);
  if (!size) throw new Error("That server does not say how large the video is, so it cannot be uploaded in parts.");
  if (size > MAX_VIDEO_BYTES) throw new Error("Videos up to 500 MB are supported.");
  return { id: videoId(u.toString()), title: niceTitle(decodeURIComponent(u.pathname.split("/").pop() || "")), caption: "", url: u.toString(), size, kind: "link", source: sid, when: new Date().toISOString() };
}
function replaceVideos(lib, sid, videos) {
  lib.videos = lib.videos.filter((v) => v.source !== sid).concat(videos).slice(0, MAX_VIDEOS);
}
function findVideo(lib, id) {
  if (id === SAMPLE.id) return lib.videos.find((v) => v.id === SAMPLE.id) || null;
  return lib.videos.find((v) => v.id === id) || null;
}
function sampleVideo(sid) {
  return Object.assign({}, SAMPLE, { source: sid, when: new Date().toISOString() });
}
function mb(bytes) {
  const n = Number(bytes || 0);
  return n >= 1024 * 1024 ? (n / (1024 * 1024)).toFixed(n >= 100 * 1024 * 1024 ? 0 : 1).replace(/\.0$/, "") + " MB" : Math.max(1, Math.round(n / 1024)) + " KB";
}
function whenWord(iso) {
  const t = Date.parse(iso || "");
  if (!t) return "";
  const d = new Date(t);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: d.getFullYear() === new Date().getFullYear() ? void 0 : "numeric" });
}
function sourceLabel(s) {
  if (!s) return "";
  if (s.kind === "github") return "GitHub \xB7 " + s.repo;
  if (s.kind === "link") return "Direct link";
  return "Sample video";
}

// ---------- moving a video to TikTok in chunks ----------
function chunkPlan(size) {
  if (size < CHUNK) return { chunk_size: size, count: 1 };
  return { chunk_size: CHUNK, count: Math.floor(size / CHUNK) };
}
function chunkRange(plan, size, i) {
  const start = i * plan.chunk_size;
  const end = i === plan.count - 1 ? size - 1 : start + plan.chunk_size - 1;
  return { start, end };
}
async function readRange(url, start, end, size) {
  const res = await fetch(url, { headers: { Range: `bytes=${start}-${end}` }, redirect: "follow" });
  if (res.status === 206) return Buffer.from(await res.arrayBuffer());
  if (res.status === 200) {
    // The host ignored the range: take the whole file (small ones only).
    if (size > 64 * 1024 * 1024) throw new Error("That host does not support partial downloads, so a video this large cannot be uploaded from it.");
    const all = Buffer.from(await res.arrayBuffer());
    return all.subarray(start, end + 1);
  }
  throw new Error(`The video host answered ${res.status} while reading the file.`);
}
async function putChunk(uploadUrl, bytes, start, end, size) {
  const put = await fetch(uploadUrl, {
    method: "PUT",
    headers: { "Content-Type": "video/mp4", "Content-Length": String(bytes.length), "Content-Range": `bytes ${start}-${end}/${size}` },
    body: bytes
  });
  if (put.status !== 201 && put.status !== 200 && put.status !== 206) throw new Error(`TikTok answered ${put.status} while receiving the video.`);
}
async function sendChunk(st, i) {
  const plan = { chunk_size: st.cs, count: st.n };
  const { start, end } = chunkRange(plan, st.size, i);
  const bytes = await readRange(st.url, start, end, st.size);
  if (bytes.length !== end - start + 1) throw new Error("The video host sent fewer bytes than it promised.");
  await putChunk(st.up, bytes, start, end, st.size);
}
async function beginUpload(user, video, draft, postInfo) {
  const plan = chunkPlan(video.size);
  const source_info = { source: "FILE_UPLOAD", video_size: video.size, chunk_size: plan.chunk_size, total_chunk_count: plan.count };
  const init = draft ? await tt("/v2/post/publish/inbox/video/init/", user.tok, { source_info }) : await tt("/v2/post/publish/video/init/", user.tok, { post_info: postInfo, source_info });
  const st = { id: init.publish_id, up: init.upload_url, url: video.url, size: video.size, cs: plan.chunk_size, n: plan.count, next: 0, v: video.id, draft: draft ? 1 : 0 };
  await sendChunk(st, 0);
  st.next = 1;
  return st;
}

// ---------- pages ----------
var TIKTOK_GLYPH = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false"><path d="M16.6 5.82A4.28 4.28 0 0 1 15.54 3h-3.09v12.4a2.59 2.59 0 0 1-2.59 2.5 2.59 2.59 0 0 1 0-5.18c.27 0 .52.04.76.12v-3.1a5.71 5.71 0 0 0-.76-.05A5.68 5.68 0 1 0 15.54 15.4V9.01a7.35 7.35 0 0 0 4.3 1.38V7.3a4.29 4.29 0 0 1-3.24-1.48z"/></svg>';
var LOCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>';
var PLAY = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false"><path d="M8 5v14l11-7z"/></svg>';
function shell(title, main, user, refreshSeconds) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
${refreshSeconds ? `<meta http-equiv="refresh" content="${Number(refreshSeconds)}">\n` : ""}<title>${esc(title)} | Shorts Media</title>
<meta name="description" content="Shorts Media: organize the short videos you keep in GitHub Releases or at a direct link, and post them to TikTok when you choose.">
<meta name="robots" content="noindex">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" href="/assets/shorts-media-app-icon.png">
<meta name="theme-color" content="#09090c">
<link rel="stylesheet" href="/assets/site.css">
<link rel="stylesheet" href="/app-assets/app.css">
</head>
<body class="app">
<a class="skip" href="#main">Skip to content</a>
<header>
  <div class="shell nav">
    <a class="brand" href="/">
      <img src="/assets/shorts-media-app-icon.png" alt="Shorts Media app icon" width="42" height="42">
      <span>Shorts Media</span>
    </a>
    <nav class="navlinks" aria-label="Support and legal">
      <a href="/how-it-works/">How it works</a>
      <a href="/support/">Support</a>
      <a href="/privacy-policy/">Privacy Policy</a>
      <a href="/terms-of-service/">Terms of Service</a>
    </nav>
  </div>
  <p class="sandbox-banner">Your videos, from GitHub Releases or a direct link — posted to TikTok only when you press Post.</p>
</header>

<main id="main">
<div class="shell app-shell">
  <div class="appbar">
    <div class="appbar-label">Creator dashboard</div>
    ${acct(user)}
  </div>
${main}
</div>
</main>

<footer>
  <div class="shell app-footer">
    <div>
      <div class="footerbrand">
        <img src="/assets/shorts-media-app-icon.png" alt="" width="40" height="40">
        <span>Shorts Media</span>
      </div>
      <p class="small">TikTok is a third-party service. Shorts Media is not endorsed by, sponsored by, or affiliated with TikTok. GitHub is a trademark of GitHub, Inc.</p>
    </div>
    <nav aria-label="More about Shorts Media">
      <a href="/how-it-works/">How it works</a>
      <a href="/data-and-privacy/">Data &amp; privacy controls</a>
    </nav>
  </div>
</footer>
</body>
</html>`;
}
function acct(user) {
  if (!user) {
    return '<div class="acct"><span class="acct-status acct-status-off"><span class="live-dot" aria-hidden="true"></span>TikTok not connected</span></div>';
  }
  return `<div class="acct">
      <div class="acct-pill">
        <img src="${esc(user.avatar)}" alt="TikTok profile photo" width="40" height="40">
        <span><span class="acct-name">${esc(user.name)}</span><span class="acct-handle">@${esc(user.user)}</span></span>
        <span class="acct-status"><span class="live-dot" aria-hidden="true"></span>TikTok connected</span>
      </div>
      <a class="btn btn-quiet" href="/app/disconnect">Disconnect TikTok</a>
    </div>`;
}
function thumb(v) {
  if (v.poster) return `<img src="${esc(v.poster)}" alt="" width="1080" height="1920">`;
  return `<div class="vthumb-blank" aria-hidden="true"><span class="vthumb-play">${PLAY}</span><span class="vthumb-kind">${esc(v.kind === "github" ? "GitHub release" : "Video link")}</span></div>`;
}
function card(v, user, src) {
  const meta = [v.length || "", v.size ? mb(v.size) : ""].filter(Boolean).join(" \xB7 ");
  const inner = `<div class="vthumb">${thumb(v)}${meta ? `<span class="dur">${esc(meta)}</span>` : ""}${user ? "" : `<span class="lock">${LOCK}Connect TikTok to post</span>`}</div>
<div class="vbody"><div class="vtitle">${esc(v.title)}</div><div class="vsub"><span class="badge ${user ? v.tooBig ? "badge-locked" : "badge-ready" : "badge-locked"}">${user ? v.tooBig ? "Too large" : "Ready" : "Not connected"}</span><span>${esc(whenWord(v.when) || "Today")}</span></div><div class="vsource">${esc(sourceLabel(src))}${v.release ? ` \xB7 ${esc(v.release)}` : ""}</div>${user && !v.tooBig ? `<a class="cta cta-post" href="/app/post/${esc(v.id)}">${TIKTOK_GLYPH}Post to TikTok</a><a class="cta cta-draft" href="/app/draft/${esc(v.id)}">${TIKTOK_GLYPH}Send as a draft</a>` : ""}</div>`;
  return `<div class="vcard">${inner}</div>`;
}
function sourcesPanel(lib) {
  const rows = lib.sources.map((s) => {
    const count = lib.videos.filter((v) => v.source === s.id).length;
    return `<li class="source-row">
      <div class="source-text"><strong>${esc(sourceLabel(s))}</strong><span class="small">${count} video${count === 1 ? "" : "s"}${s.synced ? " \xB7 checked " + esc(whenWord(s.synced)) : ""}${s.error ? ` \xB7 <span class="source-err">${esc(s.error)}</span>` : ""}</span></div>
      <div class="source-actions">
        ${s.kind === "github" ? `<form method="post" action="/app/sources"><input type="hidden" name="action" value="refresh"><input type="hidden" name="source" value="${esc(s.id)}"><button class="btn btn-small" type="submit">Check for new videos</button></form>` : ""}
        <form method="post" action="/app/sources"><input type="hidden" name="action" value="remove"><input type="hidden" name="source" value="${esc(s.id)}"><button class="btn btn-small btn-quiet" type="submit">Remove</button></form>
      </div>
    </li>`;
  }).join("");
  const hasSample = lib.sources.some((s) => s.kind === "sample");
  return `<section class="sources" aria-labelledby="sources-h2">
    <div class="sources-head"><h2 class="app-h2" id="sources-h2">Where your videos come from</h2><p class="muted">Shorts Media lists the videos it finds in each source. It never copies them anywhere; a video is only read when you post it.</p></div>
    ${rows ? `<ul class="source-list">${rows}</ul>` : '<p class="empty">No sources yet. Add one below.</p>'}
    <div class="addgrid">
      <form class="addcard" method="post" action="/app/sources">
        <input type="hidden" name="action" value="add-github">
        <label class="flabel" for="repo">GitHub repository</label>
        <input id="repo" name="repo" type="text" inputmode="url" placeholder="owner/repository" required maxlength="200" aria-describedby="repo-hint">
        <p class="hint" id="repo-hint">Every .mp4, .mov or .webm attached to a public release of that repository is added.</p>
        <button class="btn" type="submit">Add repository</button>
      </form>
      <form class="addcard" method="post" action="/app/sources">
        <input type="hidden" name="action" value="add-link">
        <label class="flabel" for="link">Direct video link</label>
        <input id="link" name="url" type="url" placeholder="https://…/video.mp4" required maxlength="2000" aria-describedby="link-hint">
        <p class="hint" id="link-hint">Any https link straight to a video file, up to 500 MB.</p>
        <button class="btn" type="submit">Add link</button>
      </form>
      ${hasSample ? "" : `<form class="addcard addcard-sample" method="post" action="/app/sources">
        <input type="hidden" name="action" value="add-sample">
        <div class="flabel">Just trying it out?</div>
        <p class="hint">Add Shorts Media's sample video and post it to see the whole flow.</p>
        <button class="btn" type="submit">Add the sample video</button>
      </form>`}
    </div>
  </section>`;
}
function library(user, lib, notice, connected, refreshSeconds) {
  const srcById = Object.fromEntries((lib.sources || []).map((s) => [s.id, s]));
  const videos = (lib.videos || []).slice().sort((a, b) => Date.parse(b.when || "") - Date.parse(a.when || ""));
  const main = `
  <div class="dash-head">
    <div>
      <div class="eyebrow">Library</div>
      <h1 class="app-h1">Your videos</h1>
      <p class="muted">${user ? "The videos Shorts Media found in your sources. Pick one, choose its settings, and post it to your TikTok account. Nothing is sent until you press Post." : "Connect your TikTok account, then add where your videos live: a GitHub repository's releases or a direct link."}</p>
    </div>
    <div class="dash-cta">
       <a class="btn btn-tiktok" href="/app/connect">${TIKTOK_GLYPH}${user ? "Connect another TikTok" : "Connect TikTok"}</a>
       <p class="small">${user ? "TikTok links whichever account is signed in on tiktok.com in this browser. To add a different account, first sign out at tiktok.com (or switch accounts there), then press Connect another." : "You will authorize Shorts Media on TikTok. Shorts Media never asks for your TikTok password."}</p>
     </div>
  </div>
  ${notice || ""}
  ${connected && connected.length > 1 ? `<div class="notice">Connected accounts: ${connected.map((a) => a.open_id === user?.open_id ? `<strong>${esc(a.handle || a.name)}</strong>` : `<a href="/app/select?open_id=${encodeURIComponent(a.open_id)}">${esc(a.handle || a.name)}</a>`).join(" \xB7 ")}</div>` : ""}
  ${user ? sourcesPanel(lib) : `<section class="sources"><div class="sources-head"><h2 class="app-h2">How it works</h2></div><ol class="howlist"><li><strong>Connect TikTok.</strong> You authorize Shorts Media on TikTok's own screen and can revoke it there at any time.</li><li><strong>Add your sources.</strong> A public GitHub repository (its release assets) or a direct link to a video file.</li><li><strong>Post when you are ready.</strong> Choose the caption, who can view it, comments, Duet, Stitch and content disclosure for each video, then press Post.</li></ol></section>`}
  ${user ? videos.length ? `<h2 class="app-h2 grid-h2">Videos <span class="count">${videos.length}</span></h2><div class="vgrid">${videos.map((v) => card(v, user, srcById[v.source])).join("")}</div>` : '<p class="empty empty-videos">No videos yet. Add a source above and they appear here.</p>' : `<div class="vgrid">${card(SAMPLE, null, { kind: "sample" })}</div>`}`;
  return shell("Your videos", main, user, refreshSeconds);
}
function previewBlock(video) {
  return `<div class="flabel" id="preview-label">Preview</div>
        <video class="preview" src="${esc(video.url)}"${video.poster ? ` poster="${esc(video.poster)}"` : ""} controls preload="metadata" playsinline aria-labelledby="preview-label video-title"></video>
        <p class="video-title" id="video-title">${esc(video.title)}</p>`;
}
function draftPage(user, video) {
  const main = `
  <div class="page-head">
    <div class="eyebrow">Content Posting API \xB7 Upload to inbox</div>
    <h1 class="app-h1">Send to your TikTok inbox as a draft</h1>
    <p class="muted page-lead">The video goes to your TikTok inbox. You finish the caption and settings in the TikTok app; nothing is published by this step.</p>
  </div>
  <form class="composer draft" action="/app/drafting" method="post">
    <input type="hidden" name="video" value="${esc(video.id)}">
    <div class="composer-cols">
      <div class="composer-preview">
        ${previewBlock(video)}
        <p class="check-line">${esc([video.length, mb(video.size)].filter(Boolean).join(" \xB7 "))}</p>
      </div>
      <div class="composer-form">
        <div class="post-account">
          <img src="${esc(user.avatar)}" alt="TikTok profile photo" width="48" height="48">
          <div>
            <div class="post-account-label">Sending to this account's inbox</div>
            <span class="acct-name">${esc(user.name)}</span>
            <span class="acct-handle">@${esc(user.user)}</span>
          </div>
        </div>
        <div class="submit-area">
          <div class="post-wrap"><button type="submit" class="btn-post">${TIKTOK_GLYPH}Send as a draft</button></div>
          <p class="post-note">Nothing is sent to TikTok until you press Send. You will get a notification in the TikTok app to finish the post.</p>
          <div class="cancel-row"><a class="btn btn-quiet" href="/app/">Cancel</a></div>
        </div>
      </div>
    </div>
  </form>`;
  return shell("Send as a draft", main, user);
}
function composer(user, video, creator) {
  const opts = creator.privacy_level_options || ["SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "PUBLIC_TO_EVERYONE"];
  const words = { SELF_ONLY: "Only me (private)", MUTUAL_FOLLOW_FRIENDS: "Friends (mutual follows)", FOLLOWER_OF_CREATOR: "Followers", PUBLIC_TO_EVERYONE: "Everyone" };
  const options = opts.map((o) => `<option value="${esc(o)}">${esc(words[o] || o)}</option>`).join("");
  const branded = opts.filter((o) => o !== "SELF_ONLY").map((o) => `<option value="${esc(o)}">${esc(words[o] || o)}</option>`).join("");
  const sw = (id, name, label, disabled, why) => `<div class="switch-row${disabled ? " is-disabled" : ""}">
              <div class="switch-text"><label for="${id}">${label}</label>${disabled ? `<p class="why" id="${id}-why">${esc(why)}</p>` : ""}</div>
              <input class="switch" type="checkbox" id="${id}" name="${name}" value="1"${disabled ? ` disabled aria-describedby="${id}-why"` : ""}>
            </div>`;
  const maxSec = creator.max_video_post_duration_sec ? Math.round(creator.max_video_post_duration_sec / 60) + ":00" : "10:00";
  const main = `
  <div class="page-head">
    <div class="eyebrow">Content Posting API \xB7 Direct Post</div>
    <h1 class="app-h1">New TikTok post</h1>
    <p class="muted page-lead">Check the video, edit the caption and choose your settings. Nothing is pre-selected for you.</p>
  </div>
  <form class="composer" action="/app/posting" method="post">
    <input type="hidden" name="video" value="${esc(video.id)}">
    <div class="composer-cols">
      <div class="composer-preview">
        ${previewBlock(video)}
        <p class="check-line">${video.length ? `Video length ${esc(video.length)} \xB7 ` : ""}${esc(mb(video.size))} \xB7 this account's limit is ${esc(maxSec)} per video</p>
      </div>

      <div class="composer-form">
        <div class="post-account">
          <img src="${esc(user.avatar)}" alt="TikTok profile photo" width="48" height="48">
          <div>
            <div class="post-account-label">Posting to this account</div>
            <span class="acct-name">${esc(user.name)}</span>
            <span class="acct-handle">@${esc(user.user)}</span>
          </div>
        </div>

        <div class="field">
          <label class="flabel" for="caption">Caption</label>
          <textarea id="caption" name="caption" rows="5" maxlength="2200" aria-describedby="caption-hint">${esc(video.caption || video.title)}</textarea>
          <p class="hint" id="caption-hint">Edit the caption before posting. Up to 2,200 characters, hashtags included.</p>
        </div>

        <div class="field privacy-standard">
          <label class="flabel" for="privacy">Who can view this video</label>
          <select id="privacy" name="privacy_level" aria-describedby="privacy-hint">
            <option value="" selected>Select who can view this video…</option>
            ${options}
          </select>
          <p class="hint" id="privacy-hint">You must choose. These are the options TikTok allows for this account.</p>
        </div>
        <div class="field privacy-branded">
          <label class="flabel" for="privacy-branded">Who can view this video</label>
          <select id="privacy-branded" name="privacy_level_branded" aria-describedby="privacy-branded-hint">
            <option value="" selected>Select who can view this video…</option>
            <option value="SELF_ONLY" disabled>Only me (not available for branded content)</option>
            ${branded}
          </select>
          <p class="hint" id="privacy-branded-hint">Branded content can't be private, so choose again from the options available.</p>
        </div>

        <fieldset class="field">
          <legend>Allow users to</legend>
          <div class="panel">
            ${sw("allow-comment", "allow_comment", "Comment", !!creator.comment_disabled, "The creator has turned off comments for their account")}
            ${sw("allow-duet", "allow_duet", "Duet", !!creator.duet_disabled, "The creator has turned off Duet for their account")}
            ${sw("allow-stitch", "allow_stitch", "Stitch", !!creator.stitch_disabled, "The creator has turned off Stitch for their account")}
          </div>
        </fieldset>

        <div class="field">
          <div class="panel">
            <div class="switch-row">
              <div class="switch-text">
                <label for="disclose">Disclose video content</label>
                <p class="why" id="disclose-why">Turn on to disclose that this video promotes goods or services in exchange for something of value. Your video could promote yourself, a third party, or both.</p>
              </div>
              <input class="switch" type="checkbox" id="disclose" name="disclose" value="1" aria-describedby="disclose-why">
            </div>
            <div class="disclose-panel">
              <p class="disclose-notice">You need to indicate if your content promotes yourself, a third party, or both.</p>
              <div class="check-row">
                <input class="tick-box" type="checkbox" id="your-brand" name="brand_organic_toggle" value="1" aria-describedby="your-brand-why">
                <div>
                  <label for="your-brand">Your brand</label>
                  <p class="why" id="your-brand-why">You are promoting yourself or your own business. This video will be classified as Brand Organic.</p>
                </div>
              </div>
              <div class="check-row">
                <input class="tick-box" type="checkbox" id="branded-content" name="brand_content_toggle" value="1" aria-describedby="branded-content-why">
                <div>
                  <label for="branded-content">Branded content</label>
                  <p class="why" id="branded-content-why">You are promoting another brand or a third party. This video will be classified as Branded Content.</p>
                </div>
              </div>
              <p class="label-line label-promo">Your photo/video will be labeled as 'Promotional content'</p>
              <p class="label-line label-paid">Your photo/video will be labeled as 'Paid partnership'</p>
            </div>
          </div>
        </div>

        <div class="submit-area">
          <p class="declaration decl-music">By posting, you agree to TikTok's <a href="https://www.tiktok.com/legal/page/global/music-usage-confirmation/en" target="_blank" rel="noopener noreferrer">Music Usage Confirmation</a>.</p>
          <p class="declaration decl-branded">By posting, you agree to TikTok's <a href="https://www.tiktok.com/legal/page/global/bc-policy/en" target="_blank" rel="noopener noreferrer">Branded Content Policy</a> and <a href="https://www.tiktok.com/legal/page/global/music-usage-confirmation/en" target="_blank" rel="noopener noreferrer">Music Usage Confirmation</a>.</p>
          <div class="post-wrap">
            <button type="submit" class="btn-post" aria-describedby="post-status post-note">${TIKTOK_GLYPH}Post to TikTok</button>
          </div>
          <div id="post-status">
            <p class="reason reason-privacy">Pick a privacy setting to continue.</p>
            <p class="reason reason-branded-privacy">Branded content can't be private. Pick a privacy setting again to continue.</p>
            <p class="reason reason-disclosure">Choose at least one disclosure option to continue.</p>
            <p class="reason-ready">Ready to post.</p>
          </div>
          <p class="post-note" id="post-note">Nothing is sent to TikTok until you press Post. Your video, caption and settings are only sent after that.</p>
          <div class="cancel-row"><a class="btn btn-quiet" href="/app/">Cancel</a></div>
        </div>
      </div>
    </div>
  </form>`;
  return shell("New TikTok post", main, user);
}
var AUDIENCE_WORDS = { SELF_ONLY: "visible only to you (Only me)", MUTUAL_FOLLOW_FRIENDS: "visible to your friends (mutual follows)", FOLLOWER_OF_CREATOR: "visible to your followers", PUBLIC_TO_EVERYONE: "visible to everyone" };
function statusThumb(video) {
  return video.poster ? `<img class="status-thumb" src="${esc(video.poster)}" alt="Video thumbnail" width="1080" height="1920">` : `<div class="status-thumb vthumb-blank" aria-hidden="true"><span class="vthumb-play">${PLAY}</span></div>`;
}
// state: uploading (part n of m still moving), processing, done, failed
function statusPage(user, video, state, detail, draft, privacy, parts) {
  const who = AUDIENCE_WORDS[privacy] || "with the privacy you chose";
  const done = state === "done";
  const failed = state === "failed";
  const uploading = state === "uploading";
  if (draft) return draftStatus(user, video, state, detail, parts);
  const main = `
  <section class="status-card ${done ? "posted" : "posting"}" aria-labelledby="status-h1">
    <div class="status-top">
      ${statusThumb(video)}
      <div>
        <div class="eyebrow">Content Posting API \xB7 Direct Post</div>
        <h1 class="status-h1" id="status-h1">${failed ? "TikTok could not post it" : done ? "Posted to TikTok" : uploading ? "Uploading to TikTok" : "Posting to TikTok"}</h1>
        <p class="status-title">${esc(video.title)}</p>
        <div class="mini-acct"><img src="${esc(user.avatar)}" alt="" width="36" height="36"><span><span class="acct-name">${esc(user.name)}</span><span class="acct-handle">@${esc(user.user)}</span></span></div>
      </div>
    </div>
    ${failed ? "" : '<div class="progress" aria-hidden="true"><span></span></div>'}
    <ol class="steps">
      <li class="step s1${uploading ? "" : " step-done"}"><span class="dot" aria-hidden="true"><span class="spin"></span><span class="tick"></span></span>${uploading ? `Uploading to TikTok — part ${parts.sent} of ${parts.total}` : "Uploaded to TikTok"}</li>
      <li class="step s2${done || failed ? " step-done" : ""}"><span class="dot" aria-hidden="true"><span class="spin"></span><span class="tick"></span></span>${done ? "TikTok processed your video" : failed ? "TikTok stopped processing" : uploading ? "TikTok will process your video" : "TikTok is processing your video…"}</li>
      <li class="step s3${done ? " step-done" : ""}"><span class="dot" aria-hidden="true"><span class="spin"></span><span class="tick"></span></span>${done ? "Posted — " + esc(who) : "Waiting for TikTok to confirm"}</li>
    </ol>
    <div class="status-note">
      ${done ? `<p>Your video is on your TikTok profile, ${esc(who)}. Open your profile to see it.</p>` : failed ? `<p>TikTok answered: ${esc(detail || "no reason given")}.</p>` : uploading ? "<p>The video is read from where you keep it and sent to TikTok in parts. Keep this page open.</p>" : "<p>This page checks with TikTok every few seconds. It usually takes under a minute.</p>"}
    </div>
    <div class="status-actions">${done ? `<a class="btn primary btn-wide" href="https://www.tiktok.com/@${esc(user.user)}">Open my TikTok profile</a> <a class="btn btn-quiet" href="/app/">Back to your videos</a>` : failed ? '<a class="btn primary btn-wide" href="/app/">Back to your videos</a>' : ""}</div>
  </section>`;
  return shell(done ? "Posted" : failed ? "Not posted" : uploading ? "Uploading" : "Posting", main, user, done || failed ? 0 : uploading ? 1 : 3);
}
function draftStatus(user, video, state, detail, parts) {
  const done = state === "done";
  const failed = state === "failed";
  const uploading = state === "uploading";
  const main = `
  <section class="status-card ${done ? "posted" : "posting"}" aria-labelledby="status-h1">
    <div class="status-top">
      ${statusThumb(video)}
      <div>
        <div class="eyebrow">Content Posting API \xB7 Upload to inbox</div>
        <h1 class="status-h1" id="status-h1">${failed ? "TikTok could not take the draft" : done ? "Draft sent to your TikTok inbox" : uploading ? "Uploading to TikTok" : "Sending to your TikTok inbox"}</h1>
        <p class="status-title">${esc(video.title)}</p>
        <div class="mini-acct"><img src="${esc(user.avatar)}" alt="" width="36" height="36"><span><span class="acct-name">${esc(user.name)}</span><span class="acct-handle">@${esc(user.user)}</span></span></div>
      </div>
    </div>
    ${failed ? "" : '<div class="progress" aria-hidden="true"><span></span></div>'}
    <ol class="steps">
      <li class="step s1${uploading ? "" : " step-done"}"><span class="dot" aria-hidden="true"><span class="spin"></span><span class="tick"></span></span>${uploading ? `Uploading to TikTok — part ${parts.sent} of ${parts.total}` : "Uploaded to TikTok"}</li>
      <li class="step s2${done || failed ? " step-done" : ""}"><span class="dot" aria-hidden="true"><span class="spin"></span><span class="tick"></span></span>${done ? "TikTok processed your video" : failed ? "TikTok stopped processing" : uploading ? "TikTok will process your video" : "TikTok is processing your video…"}</li>
      <li class="step s3${done ? " step-done" : ""}"><span class="dot" aria-hidden="true"><span class="spin"></span><span class="tick"></span></span>${done ? "In your inbox — finish it in the TikTok app" : "Waiting for TikTok to confirm"}</li>
    </ol>
    <div class="status-note">
      ${done ? "<p>Open the TikTok app: the draft is in your inbox, waiting for your caption and settings. Nothing was published.</p>" : failed ? `<p>TikTok answered: ${esc(detail || "no reason given")}.</p>` : uploading ? "<p>The video is read from where you keep it and sent to TikTok in parts. Keep this page open.</p>" : "<p>This page checks with TikTok every few seconds.</p>"}
      <p class="small">The draft waits in your TikTok inbox until you finish it.</p>
    </div>
    <div class="status-actions">${done || failed ? '<a class="btn primary btn-wide" href="/app/">Back to your videos</a>' : ""}</div>
  </section>`;
  return shell(done ? "Draft sent" : failed ? "Draft not sent" : uploading ? "Uploading" : "Sending", main, user, done || failed ? 0 : uploading ? 1 : 3);
}
function problem(user, title, text) {
  const main = `<section class="status-card posting"><div class="status-top"><div><div class="eyebrow">Shorts Media</div><h1 class="status-h1">${esc(title)}</h1><p class="status-title">${esc(text)}</p></div></div><div class="status-actions"><a class="btn primary btn-wide" href="/app/">Back to your videos</a></div></section>`;
  return shell(title, main, user);
}
function sessionFrom(rec) {
  return { open_id: rec.open_id, handle: rec.handle, name: rec.name, avatar: rec.avatar, tok: rec.access_token, exp: rec.access_expires_at };
}
function sessionUser(s) {
  return { open_id: s.open_id, handle: s.handle, name: s.name || "TikTok user", avatar: s.avatar || "/app-assets/img/avatar.svg", tok: s.tok, user: s.handle || s.name || "tiktok" };
}
function notice(text, kind) {
  return `<div class="${kind === "err" ? "notice notice-err" : "flash"}">${esc(text)}</div>`;
}

// ---------- the request handler ----------
exports.handler = async function(event) {
  const path = (event.path || "/").replace(/\/+$/, "") || "/";
  const jar = cookies(event);
  const session = verify(jar.sm_session);
  const access = verify(jar.sm_accounts);
  const owned = Array.isArray(access?.ids) ? access.ids.filter((id) => typeof id === "string").slice(0, 50) : [];
  const q = event.queryStringParameters || {};
  let user = null;
  let connected = [];
  try {
    accounts.connect(event);
    if (path.startsWith("/api/tiktok/")) {
      if (path !== "/api/tiktok/token" && path !== "/api/tiktok/accounts") return jsonPage(404, { error: "not_found" });
      if (!await accounts.verifyGithubOidc(event)) return jsonPage(401, { error: "unauthorized" });
      if (path === "/api/tiktok/accounts" && event.httpMethod === "GET") {
        const all2 = await accounts.listRecords();
        return jsonPage(200, { accounts: all2.map((a) => ({ open_id: a.open_id, handle: a.handle, name: a.name, scopes: a.scopes })) });
      }
      if (path !== "/api/tiktok/token" || event.httpMethod !== "POST") return jsonPage(405, { error: "method_not_allowed" });
      let requested;
      try {
        requested = JSON.parse(event.body || "{}");
      } catch {
        return jsonPage(400, { error: "invalid_json" });
      }
      const selector = String(requested.open_id || requested.handle || "");
      if (!selector || selector.length > 256) return jsonPage(400, { error: "account_required" });
      const all = await accounts.listRecords();
      const matches = all.filter((a) => a.open_id === selector || accounts.safeHandle(a.handle) === accounts.safeHandle(selector));
      if (matches.length !== 1) return jsonPage(404, { error: "account_not_found_or_ambiguous" });
      try {
        const fresh = await accounts.refreshRecord(matches[0].open_id, CONFIG);
        if (!fresh.scopes.split(",").includes("video.publish")) return jsonPage(403, { error: "video_publish_not_granted" });
        return jsonPage(200, { open_id: fresh.open_id, handle: fresh.handle, access_token: fresh.access_token, expires_at: fresh.access_expires_at });
      } catch {
        return jsonPage(409, { error: "reconnect_required" });
      }
    }
    let renewed = null;
    if (path !== "/auth/tiktok/callback" && session?.open_id && owned.includes(session.open_id)) {
      if (session.tok && session.exp > Date.now() + 5 * 60 * 1e3) {
        user = sessionUser(session);
      } else {
        // Token in the cookie is stale: the stored record refreshes it.
        try {
          const rec = await accounts.refreshRecord(session.open_id, CONFIG);
          user = sessionUser(sessionFrom(rec));
          renewed = sessionFrom(rec);
        } catch (e) {
          user = null;
        }
      }
    }
    connected = (await Promise.all(owned.map((id) => accounts.getRecord(id).catch(() => null)))).filter(Boolean);
    // The switcher lists every account this browser linked, even ones Blobs
    // has not caught up with yet (the cookie remembers their open_id).
    for (const id of owned) if (!connected.some((a) => a.open_id === id)) connected.push({ open_id: id, handle: "", name: "account (saving…)" });
    if (user && !connected.some((a) => a.open_id === user.open_id)) connected.unshift({ open_id: user.open_id, handle: user.handle, name: user.name });
    if (path === "/app") {
      const extra = renewed ? { "Set-Cookie": setCookie("sm_session", sign(renewed), 2592e3) } : {};
      if (!user) return page(library(null, emptyLibrary(), "", connected), extra);
      const { lib } = await loadLibrary(user.open_id);
      // A change made a moment ago may not have reached this read yet
      // (Blobs is eventually consistent): say so and look again shortly.
      const hint = verify(jar.sm_libv);
      let text = q.again === "1" ? `TikTok sent back @${user.handle || user.name} again — that account was already connected. To add another account, sign out at tiktok.com (or switch accounts there), then press Connect another TikTok.` : "";
      let refresh = 0;
      if (hint && Number(hint.t) > Number(lib.updated || 0) && Date.now() - Number(hint.t) < 30 * 1e3) {
        text = "Your last change is still being saved — this page will refresh in a moment.";
        refresh = 2;
      }
      return page(library(user, lib, text ? notice(text) : "", connected, refresh), extra);
    }
    if (path === "/app/select") {
      if (!owned.includes(String(q.open_id || ""))) return redirect("/app/");
      let rec = null;
      try {
        rec = await accounts.refreshRecord(String(q.open_id), CONFIG);
      } catch (e) {
        return page(problem(user, "That account is still being saved", "TikTok accounts take up to a minute to appear after connecting. Try again shortly."));
      }
      return redirect("/app/", { "Set-Cookie": setCookie("sm_session", sign(sessionFrom(rec)), 2592e3) });
    }
    if (path === "/app/connect") {
      const state = crypto.randomBytes(12).toString("base64url");
      const url = "https://www.tiktok.com/v2/auth/authorize/?" + new URLSearchParams({
        client_key: CONFIG.client_key,
        scope: SCOPES,
        response_type: "code",
        redirect_uri: CONFIG.redirect_uri,
        state,
        // The consent screen every time: a user who authorized before is
        // otherwise waved through, and the review has to SEE the scopes.
        disable_auto_auth: "1"
      }).toString();
      return redirect(url, { "Set-Cookie": setCookie("sm_state", state, 600) });
    }
    if (path === "/auth/tiktok/callback") {
      if (q.error) return page(problem(null, "TikTok did not connect", q.error_description || q.error));
      if (!q.code || !q.state || q.state !== jar.sm_state) return page(problem(null, "That link has expired", "Start again from Connect TikTok."));
      const res = await fetch(TT + "/v2/oauth/token/", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          client_key: CONFIG.client_key,
          client_secret: CONFIG.client_secret,
          code: q.code,
          grant_type: "authorization_code",
          redirect_uri: CONFIG.redirect_uri
        }).toString()
      });
      const tok = await res.json().catch(() => ({}));
      if (!tok.access_token || !tok.refresh_token || !tok.open_id) return page(problem(null, "TikTok did not connect", tok.error_description || tok.error || "persistent authorization unavailable"));
      const info = await tt("/v2/user/info/?fields=open_id,avatar_url,display_name", tok.access_token, void 0, "GET");
      const u = info.user || {};
      let creator = {};
      try {
        creator = await tt("/v2/post/publish/creator_info/query/", tok.access_token, {});
      } catch (e) {
        creator = {};
      }
      const saved = await accounts.saveAuthorization(tok, {
        handle: creator.creator_username || "",
        name: creator.creator_nickname || u.display_name || "TikTok user",
        avatar: creator.creator_avatar_url || u.avatar_url || "/app-assets/img/avatar.svg"
      });
      const again = owned.includes(tok.open_id);
      const nextOwned = [.../* @__PURE__ */ new Set([...owned, tok.open_id])].slice(-50);
      return {
        statusCode: 200,
        headers: BASE_HEADERS,
        multiValueHeaders: { "Set-Cookie": [
          setCookie("sm_session", sign(sessionFrom(saved)), 2592e3),
          setCookie("sm_accounts", sign({ ids: nextOwned }), 2592e3),
          setCookie("sm_state", "", 0)
        ] },
        body: `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=${SITE}/app/${again ? "?again=1" : ""}"><title>Connecting | Shorts Media</title></head><body style="background:#09090c;color:#eee;font:16px system-ui;padding:40px">Connected. Taking you back to Shorts Media…</body></html>`
      };
    }
    if (path === "/app/disconnect") {
      if (user) {
        await accounts.removeRecord(user.open_id);
        const remaining = owned.filter((id) => id !== user.open_id);
        return {
          statusCode: 302,
          headers: { Location: SITE + "/app/", "Cache-Control": "no-store" },
          multiValueHeaders: { "Set-Cookie": [setCookie("sm_session", "", 0), setCookie("sm_accounts", sign({ ids: remaining }), 2592e3)] },
          body: ""
        };
      }
      return redirect("/app/");
    }
    if (!user) return redirect("/app/");
    const sessionCookie = renewed ? { "Set-Cookie": setCookie("sm_session", sign(renewed), 2592e3) } : {};

    if (path === "/app/sources" && event.httpMethod === "POST") {
      const f = form(event);
      const { lib, etag } = await loadLibrary(user.open_id);
      let text = "";
      let kind = "ok";
      try {
        if (f.action === "add-github") {
          const repo = repoFrom(f.repo);
          if (!repo) throw new Error("Enter the repository as owner/repository (or paste its GitHub address).");
          const sid = sourceId("github", repo);
          if (!lib.sources.some((s) => s.id === sid) && lib.sources.length >= MAX_SOURCES) throw new Error(`You can have up to ${MAX_SOURCES} sources. Remove one first.`);
          const videos = await githubVideos(repo, sid);
          if (!videos.length) throw new Error(`${repo} has no public release with a video file attached (.mp4, .mov or .webm).`);
          const src = lib.sources.find((s) => s.id === sid) || { id: sid, kind: "github", repo, added: new Date().toISOString() };
          src.synced = new Date().toISOString();
          delete src.error;
          if (!lib.sources.includes(src)) lib.sources.push(src);
          replaceVideos(lib, sid, videos);
          text = `Added ${videos.length} video${videos.length === 1 ? "" : "s"} from ${repo}.`;
        } else if (f.action === "add-link") {
          const sid = sourceId("link", String(f.url || "").trim());
          if (lib.sources.some((s) => s.id === sid)) throw new Error("That link is already in your library.");
          if (lib.sources.length >= MAX_SOURCES) throw new Error(`You can have up to ${MAX_SOURCES} sources. Remove one first.`);
          const video = await linkVideo(f.url, sid);
          lib.sources.push({ id: sid, kind: "link", url: video.url, added: new Date().toISOString(), synced: new Date().toISOString() });
          replaceVideos(lib, sid, [video]);
          text = `Added ${video.title}.`;
        } else if (f.action === "add-sample") {
          const sid = sourceId("sample", "urban-growth");
          if (!lib.sources.some((s) => s.id === sid)) {
            lib.sources.push({ id: sid, kind: "sample", added: new Date().toISOString(), synced: new Date().toISOString() });
            replaceVideos(lib, sid, [sampleVideo(sid)]);
          }
          text = "Added the sample video.";
        } else if (f.action === "refresh") {
          const src = lib.sources.find((s) => s.id === String(f.source || ""));
          if (!src) throw new Error("That source is not in your library.");
          if (src.kind === "github") {
            try {
              const videos = await githubVideos(src.repo, src.id);
              replaceVideos(lib, src.id, videos);
              src.synced = new Date().toISOString();
              delete src.error;
              text = `${src.repo}: ${videos.length} video${videos.length === 1 ? "" : "s"} found.`;
            } catch (e) {
              src.error = String(e.message || e);
              throw e;
            }
          }
        } else if (f.action === "remove") {
          const sid = String(f.source || "");
          if (!lib.sources.some((s) => s.id === sid)) throw new Error("That source is not in your library.");
          lib.sources = lib.sources.filter((s) => s.id !== sid);
          lib.videos = lib.videos.filter((v) => v.source !== sid);
          text = "Removed.";
        } else {
          throw new Error("Unknown action.");
        }
      } catch (e) {
        text = String(e && e.message || e);
        kind = "err";
      }
      let saved = lib;
      if (kind === "ok") saved = await saveLibrary(user.open_id, lib, etag);
      const cookiesOut = [setCookie("sm_libv", sign({ t: saved.updated || 0 }), 60)];
      if (renewed) cookiesOut.push(setCookie("sm_session", sign(renewed), 2592e3));
      return { statusCode: 200, headers: BASE_HEADERS, multiValueHeaders: { "Set-Cookie": cookiesOut }, body: library(user, saved, notice(text, kind), connected) };
    }

    const postMatch = path.match(/^\/app\/(post|draft)\/([A-Za-z0-9_-]{1,64})$/);
    if (postMatch) {
      const { lib } = await loadLibrary(user.open_id);
      const video = findVideo(lib, postMatch[2]);
      if (!video) return page(problem(user, "That video is not in your library", "It may have been removed from its source. Check the source on your videos page."), sessionCookie);
      if (video.tooBig) return page(problem(user, "That video is too large", "Videos up to 500 MB are supported."), sessionCookie);
      if (postMatch[1] === "draft") return page(draftPage(user, video), sessionCookie);
      let creator = {};
      try {
        creator = await tt("/v2/post/publish/creator_info/query/", user.tok, {});
      } catch (e) {
        creator = {};
      }
      return page(composer(user, video, creator), sessionCookie);
    }
    if ((path === "/app/posting" || path === "/app/drafting") && event.httpMethod === "POST") {
      const f = form(event);
      const draft = path === "/app/drafting";
      const { lib } = await loadLibrary(user.open_id);
      const video = findVideo(lib, String(f.video || ""));
      if (!video) return page(problem(user, "That video is not in your library", "Go back to your videos and pick one."));
      let postInfo = null;
      let privacy = "";
      if (!draft) {
        const branded = f.brand_content_toggle === "1";
        privacy = branded ? f.privacy_level_branded : f.privacy_level;
        if (!privacy) return page(problem(user, "Pick who can view it", "Choose a privacy setting, then post again."));
        if (f.disclose === "1" && !branded && f.brand_organic_toggle !== "1") return page(problem(user, "Say what the video promotes", "Choose at least one disclosure option, then post again."));
        postInfo = {
          title: String(f.caption || "").slice(0, 2200),
          privacy_level: privacy,
          disable_comment: f.allow_comment !== "1",
          disable_duet: f.allow_duet !== "1",
          disable_stitch: f.allow_stitch !== "1",
          video_cover_timestamp_ms: 1e3,
          brand_content_toggle: branded,
          brand_organic_toggle: f.brand_organic_toggle === "1"
        };
      }
      const st = await beginUpload(user, video, draft, postInfo);
      const to = "/app/status?id=" + encodeURIComponent(st.id) + "&v=" + encodeURIComponent(video.id) + (draft ? "&draft=1" : "&p=" + encodeURIComponent(privacy));
      // The remaining parts move on the status page, one per refresh.
      return redirect(to, { "Set-Cookie": setCookie("sm_upload", sign(st), 3600) });
    }
    if (path === "/app/status") {
      const draft = q.draft === "1";
      const { lib } = await loadLibrary(user.open_id);
      const video = findVideo(lib, String(q.v || "")) || { title: "Your video", poster: "", kind: "link" };
      const st = verify(jar.sm_upload);
      if (st && st.id === String(q.id || "") && st.next < st.n) {
        try {
          await sendChunk(st, st.next);
        } catch (e) {
          return page(statusPage(user, video, "failed", String(e.message || e), draft, q.p, null), { "Set-Cookie": setCookie("sm_upload", "", 0) });
        }
        st.next += 1;
        const finished = st.next >= st.n;
        return page(statusPage(user, video, finished ? "processing" : "uploading", "", draft, q.p, { sent: st.next, total: st.n }), { "Set-Cookie": finished ? setCookie("sm_upload", "", 0) : setCookie("sm_upload", sign(st), 3600) });
      }
      const res = await tt("/v2/post/publish/status/fetch/", user.tok, { publish_id: String(q.id || "") });
      const s = String(res.status || "");
      if (s === "PUBLISH_COMPLETE" || s === "SEND_TO_USER_INBOX") return page(statusPage(user, video, "done", "", draft, q.p, null));
      if (s === "FAILED") return page(statusPage(user, video, "failed", res.fail_reason || "", draft, q.p, null));
      return page(statusPage(user, video, "processing", "", draft, q.p, null));
    }
    return redirect("/app/");
  } catch (e) {
    const said = String(e && e.message || e);
    if (said.indexOf("unaudited_client_can_only_post_to_private_accounts") === 0) {
      return page(problem(
        user,
        "Your TikTok account needs to be private for this",
        "Until TikTok audits Shorts Media for public posting, TikTok only lets it post to an account set to Private. In TikTok: Settings and privacy › Privacy › Private account. Then post again."
      ));
    }
    return page(problem(user, "Something went wrong", said));
  }
};
