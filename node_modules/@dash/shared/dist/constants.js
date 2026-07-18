/** Application-wide constants shared across clients and services. */
export const APP_NAME = 'DASH';
export const APP_VERSION = '0.1.0';
export const API_PREFIX = '/api/v1';
export const API_ROUTES = {
    HEALTH: `${API_PREFIX}/health`,
    WEBSOCKET: `${API_PREFIX}/ws`,
};
export const DEFAULT_BACKEND_URL = 'http://localhost:8000';
export const DEFAULT_WS_URL = 'ws://localhost:8000';
export const SUPPORTED_PLATFORMS = ['win32', 'darwin', 'linux'];
//# sourceMappingURL=constants.js.map