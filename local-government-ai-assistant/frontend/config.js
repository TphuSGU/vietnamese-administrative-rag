/*
 * Runtime configuration for the static frontend.
 *
 * Override before this file loads, or pass ?api=https://api.example.com/api/v1.
 * Default keeps local development working when the UI is served from :3000
 * and FastAPI runs on :8000.
 */
(function () {
    const params = new URLSearchParams(window.location.search);
    const apiOverride = params.get('api');
    const protocol = window.location.protocol === 'file:' ? 'http:' : window.location.protocol;
    const host = window.location.hostname || 'localhost';
    const localApi = `${protocol}//${host}:8000/api/v1`;

    window.APP_CONFIG = window.APP_CONFIG || {};
    window.APP_CONFIG.API_BASE_URL =
        apiOverride || window.APP_CONFIG.API_BASE_URL || localApi;
})();
