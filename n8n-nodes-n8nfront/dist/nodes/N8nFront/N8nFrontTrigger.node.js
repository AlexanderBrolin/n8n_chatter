"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.N8nFrontTrigger = void 0;
class N8nFrontTrigger {
    constructor() {
        this.description = {
            displayName: 'N8nFront Trigger',
            name: 'n8nFrontTrigger',
            icon: 'file:n8nfront.svg',
            group: ['trigger'],
            version: 1,
            subtitle: 'Получает события из чата',
            description: 'Срабатывает при получении сообщения или callback от пользователя в N8nFront',
            defaults: {
                name: 'N8nFront Trigger',
            },
            inputs: [],
            outputs: ['main'],
            credentials: [
                {
                    name: 'n8nFrontApi',
                    required: true,
                },
            ],
            webhooks: [
                {
                    name: 'default',
                    httpMethod: 'POST',
                    responseMode: 'onReceived',
                    path: 'webhook',
                },
            ],
            properties: [
                {
                    displayName: 'Events',
                    name: 'events',
                    type: 'multiOptions',
                    default: ['message'],
                    options: [
                        {
                            name: 'Сообщение',
                            value: 'message',
                            description: 'Текстовое сообщение от пользователя',
                        },
                        {
                            name: 'Документ',
                            value: 'document',
                            description: 'Пользователь отправил файл',
                        },
                        {
                            name: 'Фото',
                            value: 'photo',
                            description: 'Пользователь отправил изображение',
                        },
                        {
                            name: 'Голосовое сообщение',
                            value: 'voice',
                            description: 'Пользователь отправил голосовое сообщение',
                        },
                        {
                            name: 'Видео-кружок',
                            value: 'video_note',
                            description: 'Пользователь отправил видео-кружок',
                        },
                        {
                            name: 'Callback (инлайн-кнопка)',
                            value: 'callback_query',
                            description: 'Пользователь нажал инлайн-кнопку',
                        },
                    ],
                    description: 'Типы событий для обработки',
                },
            ],
        };
        this.webhookMethods = {
            default: {
                async checkExists() {
                    const credentials = await this.getCredentials('n8nFrontApi');
                    const webhookUrl = this.getNodeWebhookUrl('default');
                    try {
                        const response = await this.helpers.httpRequest({
                            method: 'GET',
                            url: `${credentials.baseUrl.replace(/\/+$/, "")}/api/bot/${credentials.botToken}/getWebhookInfo`,
                        });
                        return response?.result?.url === webhookUrl;
                    }
                    catch {
                        return false;
                    }
                },
                async create() {
                    const credentials = await this.getCredentials('n8nFrontApi');
                    const webhookUrl = this.getNodeWebhookUrl('default');
                    await this.helpers.httpRequest({
                        method: 'POST',
                        url: `${credentials.baseUrl.replace(/\/+$/, "")}/api/bot/${credentials.botToken}/setWebhook`,
                        body: { url: webhookUrl },
                        headers: { 'Content-Type': 'application/json' },
                    });
                    return true;
                },
                async delete() {
                    const credentials = await this.getCredentials('n8nFrontApi');
                    try {
                        await this.helpers.httpRequest({
                            method: 'POST',
                            url: `${credentials.baseUrl.replace(/\/+$/, "")}/api/bot/${credentials.botToken}/deleteWebhook`,
                        });
                    }
                    catch {
                        // Ignore errors on cleanup
                    }
                    return true;
                },
            },
        };
    }
    async webhook() {
        const body = this.getBodyData();
        const events = this.getNodeParameter('events', []);
        // Handle callback_query
        if (body.callback_query) {
            if (!events.includes('callback_query')) {
                return { noWebhookResponse: true };
            }
            return {
                workflowData: [this.helpers.returnJsonArray(body)],
            };
        }
        // Handle message
        if (body.message) {
            const msg = body.message;
            const hasDocument = !!msg.document;
            const hasPhoto = msg.photo && msg.photo.length > 0;
            const hasVoice = !!msg.voice;
            const hasVideoNote = !!msg.video_note;
            const isText = !hasDocument && !hasPhoto && !hasVoice && !hasVideoNote;
            if (isText && !events.includes('message')) {
                return { noWebhookResponse: true };
            }
            if (hasDocument && !events.includes('document')) {
                return { noWebhookResponse: true };
            }
            if (hasPhoto && !events.includes('photo')) {
                return { noWebhookResponse: true };
            }
            if (hasVoice && !events.includes('voice')) {
                return { noWebhookResponse: true };
            }
            if (hasVideoNote && !events.includes('video_note')) {
                return { noWebhookResponse: true };
            }
        }
        return {
            workflowData: [this.helpers.returnJsonArray(body)],
        };
    }
}
exports.N8nFrontTrigger = N8nFrontTrigger;
//# sourceMappingURL=N8nFrontTrigger.node.js.map