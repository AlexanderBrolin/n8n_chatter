"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.N8nFrontApi = void 0;
class N8nFrontApi {
    constructor() {
        this.name = 'n8nFrontApi';
        this.displayName = 'N8nFront Bot API';
        this.documentationUrl = '';
        this.properties = [
            {
                displayName: 'Base URL',
                name: 'baseUrl',
                type: 'string',
                default: '',
                placeholder: 'https://chat.example.com',
                description: 'URL вашего N8nFront сервера (без /api/bot)',
                required: true,
            },
            {
                displayName: 'Bot Token',
                name: 'botToken',
                type: 'string',
                typeOptions: { password: true },
                default: '',
                description: 'API-токен бота (из админки N8nFront)',
                required: true,
            },
        ];
        this.test = {
            request: {
                url: '={{$credentials.baseUrl.replace(/\\/+$/, "") + "/api/bot/" + $credentials.botToken + "/getMe"}}',
                method: 'GET',
            },
        };
    }
}
exports.N8nFrontApi = N8nFrontApi;
//# sourceMappingURL=N8nFrontApi.credentials.js.map