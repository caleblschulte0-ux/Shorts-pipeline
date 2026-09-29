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
var CONFIG = {
  client_key: process.env.TIKTOK_CLIENT_KEY || "__TIKTOK_CLIENT_KEY__",
  client_secret: process.env.TIKTOK_CLIENT_SECRET || "__TIKTOK_CLIENT_SECRET__",
  redirect_uri: process.env.TIKTOK_REDIRECT_URI || "https://shorts-media.netlify.app/auth/tiktok/callback/",
  cookie_secret: process.env.SM_COOKIE_SECRET || "__SM_COOKIE_SECRET__"
};
var SITE = "https://shorts-media.netlify.app";
var TT = "https://open.tiktokapis.com";
var SCOPES = "user.info.basic,video.upload,video.publish";
var VIDEO = {
  id: "urban-growth",
  title: "Urban Growth Just Hit A 50-Year Low Of 1.36%",
  caption: "Everyone assumes cities are exploding faster than ever \u2014 but the world's urban growth rate just fell to its slowest pace in over 50 years.\n\n#data #cities #urbanization #explained",
  length: "1:36",
  file: SITE + "/app-assets/media/urban-growth.mp4",
  poster: "/app-assets/media/urban-growth-poster.png"
};
var LIBRARY = [
  { id: "cargo-ships", title: "Cargo Ships Quietly Got Six Times Bigger", length: "0:58", poster: "/app-assets/img/poster-cargo-ships.svg", when: "Yesterday" },
  { id: "ocean-floor", title: "We\u2019ve Mapped More Of Mars Than Our Own Ocean Floor", length: "1:12", poster: "/app-assets/img/poster-ocean-floor.svg", when: "2 days ago" },
  { id: "drinkable-water", title: "How Much Of Earth\u2019s Water You Can Actually Drink", length: "1:04", poster: "/app-assets/img/poster-drinkable-water.svg", when: "3 days ago" }
];
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
  "Content-Security-Policy": "default-src 'self'; img-src 'self' data: https:; media-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'none'; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
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
var TIKTOK_GLYPH = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false"><path d="M16.6 5.82A4.28 4.28 0 0 1 15.54 3h-3.09v12.4a2.59 2.59 0 0 1-2.59 2.5 2.59 2.59 0 0 1 0-5.18c.27 0 .52.04.76.12v-3.1a5.71 5.71 0 0 0-.76-.05A5.68 5.68 0 1 0 15.54 15.4V9.01a7.35 7.35 0 0 0 4.3 1.38V7.3a4.29 4.29 0 0 1-3.24-1.48z"/></svg>';
var LOCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>';
function shell(title, main, user) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)} | Shorts Media</title>
<meta name="description" content="Shorts Media creator dashboard.">
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
      <a href="/support/">Support</a>
      <a href="/privacy-policy/">Privacy Policy</a>
      <a href="/terms-of-service/">Terms of Service</a>
    </nav>
  </div>
  <p class="sandbox-banner">TikTok Live app \u2014 connect a TikTok account to publish with the access you approve.</p>
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
      <p class="small">TikTok is a third-party service. Shorts Media is not endorsed by, sponsored by, or affiliated with TikTok.</p>
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
function card(v, user, primary) {
  const inner = `<div class="vthumb"><img src="${esc(v.poster)}" alt="" width="1080" height="1920"><span class="dur">${esc(v.length)}</span>${user ? "" : `<span class="lock">${LOCK}Connect TikTok to share</span>`}</div>
<div class="vbody"><div class="vtitle">${esc(v.title)}</div><div class="vsub"><span class="badge ${user ? "badge-ready" : "badge-locked"}">${user ? "Ready" : "Not connected"}</span><span>${esc(v.when || "Today")}</span></div>${user && primary ? `<a class="cta cta-post" href="/app/post/${esc(v.id)}">${TIKTOK_GLYPH}Post to TikTok</a><a class="cta cta-draft" href="/app/draft/${esc(v.id)}">${TIKTOK_GLYPH}Send as a draft</a>` : ""}</div>`;
  return `<div class="vcard">${inner}</div>`;
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
        <div class="flabel" id="preview-label">Preview</div>
        <video class="preview" src="/app-assets/media/${esc(video.id)}.mp4" poster="${esc(video.poster)}" controls preload="metadata" playsinline aria-labelledby="preview-label video-title"></video>
        <p class="video-title" id="video-title">${esc(video.title)}</p>
        <p class="check-line">Video length ${esc(video.length)}</p>
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
function library(user, notice, connected) {
  const main = `
  <div class="dash-head">
    <div>
      <div class="eyebrow">Library</div>
      <h1 class="app-h1">Your Shorts</h1>
      <p class="muted">${user ? "Post a short straight to your TikTok account. Nothing is sent until you press Post." : "Connect your TikTok account to post these shorts to TikTok."}</p>
    </div>
    <div class="dash-cta">
       <a class="btn btn-tiktok" href="/app/connect">${TIKTOK_GLYPH}${user ? "Connect another TikTok" : "Connect TikTok"}</a>
       <p class="small">You will authorize Shorts Media on TikTok. Shorts Media never asks for your TikTok password.</p>
     </div>
  </div>
  ${notice || ""}
  ${connected && connected.length > 1 ? `<div class="notice">Connected accounts: ${connected.map((a) => a.open_id === user?.open_id ? `<strong>${esc(a.handle || a.name)}</strong>` : `<a href="/app/select?open_id=${encodeURIComponent(a.open_id)}">${esc(a.handle || a.name)}</a>`).join(" \xB7 ")}</div>` : ""}
  <div class="vgrid">
    ${card(Object.assign({ when: "Today" }, VIDEO), user, true)}${LIBRARY.map((v) => card(v, user, false)).join("")}
  </div>`;
  return shell("Your Shorts", main, user);
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
        <div class="flabel" id="preview-label">Preview</div>
        <video class="preview" src="/app-assets/media/${esc(video.id)}.mp4" poster="${esc(video.poster)}" controls preload="metadata" playsinline aria-labelledby="preview-label video-title"></video>
        <p class="video-title" id="video-title">${esc(video.title)}</p>
        <p class="check-line">Video length ${esc(video.length)} \xB7 within this account's ${esc(maxSec)} maximum</p>
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
          <textarea id="caption" name="caption" rows="5" maxlength="2200" aria-describedby="caption-hint">${esc(video.caption)}</textarea>
          <p class="hint" id="caption-hint">Edit the caption before posting. Up to 2,200 characters, hashtags included.</p>
        </div>

        <div class="field privacy-standard">
          <label class="flabel" for="privacy">Who can view this video</label>
          <select id="privacy" name="privacy_level" aria-describedby="privacy-hint">
            <option value="" selected>Select who can view this video\u2026</option>
            ${options}
          </select>
          <p class="hint" id="privacy-hint">You must choose. These are the options TikTok allows for this account.</p>
        </div>
        <div class="field privacy-branded">
          <label class="flabel" for="privacy-branded">Who can view this video</label>
          <select id="privacy-branded" name="privacy_level_branded" aria-describedby="privacy-branded-hint">
            <option value="" selected>Select who can view this video\u2026</option>
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
function statusPage(user, video, state, detail, draft) {
  const done = state === "done";
  const failed = state === "failed";
  if (draft) return draftStatus(user, video, state, detail);
  const main = `
  <section class="status-card ${done ? "posted" : "posting"}" aria-labelledby="status-h1">
    <div class="status-top">
      <img class="status-thumb" src="${esc(video.poster)}" alt="Video thumbnail" width="1080" height="1920">
      <div>
        <div class="eyebrow">Content Posting API \xB7 Direct Post</div>
        <h1 class="status-h1" id="status-h1">${failed ? "TikTok could not post it" : done ? "Posted to TikTok" : "Posting to TikTok"}</h1>
        <p class="status-title">${esc(video.title)}</p>
        <div class="mini-acct"><img src="${esc(user.avatar)}" alt="" width="36" height="36"><span><span class="acct-name">${esc(user.name)}</span><span class="acct-handle">@${esc(user.user)}</span></span></div>
      </div>
    </div>
    ${failed ? "" : '<div class="progress" aria-hidden="true"><span></span></div>'}
    <ol class="steps">
      <li class="step s1 step-done"><span class="dot" aria-hidden="true"><span class="tick"></span></span>Uploaded to TikTok</li>
      <li class="step s2${state === "uploading" || state === "processing" ? "" : " step-done"}"><span class="dot" aria-hidden="true"><span class="spin"></span><span class="tick"></span></span>${done ? "TikTok processed your video" : failed ? "TikTok stopped processing" : "TikTok is processing your video\u2026"}</li>
      <li class="step s3${done ? " step-done" : ""}"><span class="dot" aria-hidden="true"><span class="spin"></span><span class="tick"></span></span>${done ? "Posted \u2014 visible only to you" : "Waiting for TikTok to confirm"}</li>
    </ol>
    <div class="status-note">
      ${done ? "<p>Your video is on your TikTok profile, visible only to you (Only me). Open your profile to see it.</p>" : failed ? `<p>TikTok answered: ${esc(detail || "no reason given")}.</p>` : "<p>This page checks with TikTok every few seconds. It usually takes under a minute.</p>"}
      <p class="small">Until TikTok audits Shorts Media for public posting, TikTok keeps API posts private (Only me).</p>
    </div>
    <div class="status-actions">${done ? `<a class="btn primary btn-wide" href="https://www.tiktok.com/@${esc(user.user)}">Open my TikTok profile</a> <a class="btn btn-quiet" href="/app/">Back to your Shorts</a>` : failed ? '<a class="btn primary btn-wide" href="/app/">Back to your Shorts</a>' : ""}</div>
  </section>`;
  const html = shell(done ? "Posted" : failed ? "Not posted" : "Posting", main, user);
  if (done || failed) return html;
  return html.replace("<title>", '<meta http-equiv="refresh" content="3">\n<title>');
}
function draftStatus(user, video, state, detail) {
  const done = state === "done";
  const failed = state === "failed";
  const main = `
  <section class="status-card ${done ? "posted" : "posting"}" aria-labelledby="status-h1">
    <div class="status-top">
      <img class="status-thumb" src="${esc(video.poster)}" alt="Video thumbnail" width="1080" height="1920">
      <div>
        <div class="eyebrow">Content Posting API \xB7 Upload to inbox</div>
        <h1 class="status-h1" id="status-h1">${failed ? "TikTok could not take the draft" : done ? "Draft sent to your TikTok inbox" : "Sending to your TikTok inbox"}</h1>
        <p class="status-title">${esc(video.title)}</p>
        <div class="mini-acct"><img src="${esc(user.avatar)}" alt="" width="36" height="36"><span><span class="acct-name">${esc(user.name)}</span><span class="acct-handle">@${esc(user.user)}</span></span></div>
      </div>
    </div>
    ${failed ? "" : '<div class="progress" aria-hidden="true"><span></span></div>'}
    <ol class="steps">
      <li class="step s1 step-done"><span class="dot" aria-hidden="true"><span class="tick"></span></span>Uploaded to TikTok</li>
      <li class="step s2${done || failed ? " step-done" : ""}"><span class="dot" aria-hidden="true"><span class="spin"></span><span class="tick"></span></span>${done ? "TikTok processed your video" : failed ? "TikTok stopped processing" : "TikTok is processing your video\u2026"}</li>
      <li class="step s3${done ? " step-done" : ""}"><span class="dot" aria-hidden="true"><span class="spin"></span><span class="tick"></span></span>${done ? "In your inbox \u2014 finish it in the TikTok app" : "Waiting for TikTok to confirm"}</li>
    </ol>
    <div class="status-note">
      ${done ? "<p>Open the TikTok app: the draft is in your inbox, waiting for your caption and settings. Nothing was published.</p>" : failed ? `<p>TikTok answered: ${esc(detail || "no reason given")}.</p>` : "<p>This page checks with TikTok every few seconds.</p>"}
      <p class="small">The draft waits in your TikTok inbox until you finish it.</p>
    </div>
    <div class="status-actions">${done || failed ? '<a class="btn primary btn-wide" href="/app/">Back to your Shorts</a>' : ""}</div>
  </section>`;
  const html = shell(done ? "Draft sent" : failed ? "Draft not sent" : "Sending", main, user);
  if (done || failed) return html;
  return html.replace("<title>", '<meta http-equiv="refresh" content="3">\n<title>');
}
function problem(user, title, text) {
  const main = `<section class="status-card posting"><div class="status-top"><div><div class="eyebrow">Shorts Media</div><h1 class="status-h1">${esc(title)}</h1><p class="status-title">${esc(text)}</p></div></div><div class="status-actions"><a class="btn primary btn-wide" href="/app/">Back to your Shorts</a></div></section>`;
  return shell(title, main, user);
}
function sessionFrom(rec) {
  return { open_id: rec.open_id, handle: rec.handle, name: rec.name, avatar: rec.avatar, tok: rec.access_token, exp: rec.access_expires_at };
}
function sessionUser(s) {
  return { open_id: s.open_id, handle: s.handle, name: s.name || "TikTok user", avatar: s.avatar || "/app-assets/img/avatar.svg", tok: s.tok, user: s.handle || s.name || "tiktok" };
}
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
    if (user && !connected.some((a) => a.open_id === user.open_id)) connected.unshift({ open_id: user.open_id, handle: user.handle, name: user.name });
    if (renewed && path === "/app") return page(library(user, "", connected), { "Set-Cookie": setCookie("sm_session", sign(renewed), 2592e3) });
    if (path === "/app") return page(library(user, "", connected));
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
      const nextOwned = [.../* @__PURE__ */ new Set([...owned, tok.open_id])].slice(-50);
      return {
        statusCode: 200,
        headers: BASE_HEADERS,
        multiValueHeaders: { "Set-Cookie": [
          setCookie("sm_session", sign(sessionFrom(saved)), 2592e3),
          setCookie("sm_accounts", sign({ ids: nextOwned }), 2592e3),
          setCookie("sm_state", "", 0)
        ] },
        body: `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=${SITE}/app/"><title>Connecting | Shorts Media</title></head><body style="background:#09090c;color:#eee;font:16px system-ui;padding:40px">Connected. Taking you back to Shorts Media\u2026</body></html>`
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
    if (path === "/app/post/" + VIDEO.id) {
      let creator = {};
      try {
        creator = await tt("/v2/post/publish/creator_info/query/", user.tok, {});
      } catch (e) {
        creator = {};
      }
      return page(composer(user, VIDEO, creator));
    }
    if (path === "/app/posting" && event.httpMethod === "POST") {
      const f = form(event);
      const branded = f.brand_content_toggle === "1";
      const privacy = branded ? f.privacy_level_branded : f.privacy_level;
      if (!privacy) return page(problem(user, "Pick who can view it", "Choose a privacy setting, then post again."));
      if (f.disclose === "1" && !branded && f.brand_organic_toggle !== "1") return page(problem(user, "Say what the video promotes", "Choose at least one disclosure option, then post again."));
      const video = await fetch(VIDEO.file);
      const bytes = Buffer.from(await video.arrayBuffer());
      const init = await tt("/v2/post/publish/video/init/", user.tok, {
        post_info: {
          title: String(f.caption || "").slice(0, 2200),
          privacy_level: privacy,
          disable_comment: f.allow_comment !== "1",
          disable_duet: f.allow_duet !== "1",
          disable_stitch: f.allow_stitch !== "1",
          video_cover_timestamp_ms: 1e3,
          brand_content_toggle: branded,
          brand_organic_toggle: f.brand_organic_toggle === "1"
        },
        source_info: { source: "FILE_UPLOAD", video_size: bytes.length, chunk_size: bytes.length, total_chunk_count: 1 }
      });
      const put = await fetch(init.upload_url, {
        method: "PUT",
        headers: {
          "Content-Type": "video/mp4",
          "Content-Length": String(bytes.length),
          "Content-Range": `bytes 0-${bytes.length - 1}/${bytes.length}`
        },
        body: bytes
      });
      if (put.status !== 201 && put.status !== 200) return page(problem(user, "The upload did not take", `TikTok answered ${put.status}.`));
      return redirect("/app/status?id=" + encodeURIComponent(init.publish_id));
    }
    if (path === "/app/draft/" + VIDEO.id) return page(draftPage(user, VIDEO));
    if (path === "/app/drafting" && event.httpMethod === "POST") {
      const video = await fetch(VIDEO.file);
      const bytes = Buffer.from(await video.arrayBuffer());
      const init = await tt("/v2/post/publish/inbox/video/init/", user.tok, {
        source_info: { source: "FILE_UPLOAD", video_size: bytes.length, chunk_size: bytes.length, total_chunk_count: 1 }
      });
      const put = await fetch(init.upload_url, {
        method: "PUT",
        headers: {
          "Content-Type": "video/mp4",
          "Content-Length": String(bytes.length),
          "Content-Range": `bytes 0-${bytes.length - 1}/${bytes.length}`
        },
        body: bytes
      });
      if (put.status !== 201 && put.status !== 200) return page(problem(user, "The upload did not take", `TikTok answered ${put.status}.`));
      return redirect("/app/status?draft=1&id=" + encodeURIComponent(init.publish_id));
    }
    if (path === "/app/status") {
      const draft = q.draft === "1";
      const st = await tt("/v2/post/publish/status/fetch/", user.tok, { publish_id: String(q.id || "") });
      const s = String(st.status || "");
      if (s === "PUBLISH_COMPLETE" || s === "SEND_TO_USER_INBOX") return page(statusPage(user, VIDEO, "done", "", draft));
      if (s === "FAILED") return page(statusPage(user, VIDEO, "failed", st.fail_reason || "", draft));
      return page(statusPage(user, VIDEO, s === "PROCESSING_UPLOAD" ? "uploading" : "processing", "", draft));
    }
    return redirect("/app/");
  } catch (e) {
    const said = String(e && e.message || e);
    if (said.indexOf("unaudited_client_can_only_post_to_private_accounts") === 0) {
      return page(problem(
        user,
        "Your TikTok account needs to be private for this",
        "Until TikTok audits Shorts Media for public posting, TikTok only lets it post to an account set to Private. In TikTok: Settings and privacy \u203A Privacy \u203A Private account. Then post again."
      ));
    }
    return page(problem(user, "Something went wrong", said));
  }
};
