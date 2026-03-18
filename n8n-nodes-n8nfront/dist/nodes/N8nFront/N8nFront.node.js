"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.N8nFront = void 0;
const operationFields = [
    {
        displayName: 'Operation',
        name: 'operation',
        type: 'options',
        noDataExpression: true,
        default: 'sendMessage',
        options: [
            {
                name: 'Отправить сообщение',
                value: 'sendMessage',
                action: 'Отправить текстовое сообщение',
                description: 'Отправить текстовое сообщение в чат',
            },
            {
                name: 'Редактировать сообщение',
                value: 'editMessageText',
                action: 'Редактировать текст сообщения',
                description: 'Изменить текст ранее отправленного сообщения бота',
            },
            {
                name: 'Удалить сообщение',
                value: 'deleteMessage',
                action: 'Удалить сообщение',
                description: 'Удалить сообщение в чате (soft delete)',
            },
            {
                name: 'Отправить документ',
                value: 'sendDocument',
                action: 'Отправить файл',
                description: 'Отправить файл-документ в чат',
            },
            {
                name: 'Отправить фото',
                value: 'sendPhoto',
                action: 'Отправить изображение',
                description: 'Отправить изображение в чат',
            },
            {
                name: 'Скачать файл',
                value: 'downloadFile',
                action: 'Скачать файл как binary',
                description: 'Скачать файл по file_id как бинарные данные для обработки в n8n',
            },
            {
                name: 'Получить файл (инфо)',
                value: 'getFile',
                action: 'Получить информацию о файле',
                description: 'Получить метаданные файла и ссылку на скачивание',
            },
            {
                name: 'Индикатор набора',
                value: 'sendChatAction',
                action: 'Показать индикатор набора',
                description: 'Показать индикатор «бот печатает...» в чате',
            },
            {
                name: 'Информация о боте',
                value: 'getMe',
                action: 'Получить информацию о боте',
                description: 'Возвращает информацию о текущем боте',
            },
        ],
    },
    // --- Chat ID (shared by most operations) ---
    {
        displayName: 'Chat ID',
        name: 'chatId',
        type: 'string',
        default: '',
        required: true,
        description: 'ID чата (conversation). Берётся из триггера: {{ $json.message.chat.id }}',
        displayOptions: {
            show: {
                operation: [
                    'sendMessage', 'editMessageText', 'deleteMessage',
                    'sendDocument', 'sendPhoto', 'sendChatAction',
                ],
            },
        },
    },
    // --- Message ID (for edit / delete) ---
    {
        displayName: 'Message ID',
        name: 'messageId',
        type: 'number',
        default: 0,
        required: true,
        description: 'ID сообщения для редактирования/удаления. Берётся из триггера: {{ $json.message.message_id }}',
        displayOptions: { show: { operation: ['editMessageText', 'deleteMessage'] } },
    },
    // --- Text (sendMessage, editMessageText) ---
    {
        displayName: 'Текст',
        name: 'text',
        type: 'string',
        typeOptions: { rows: 4 },
        default: '',
        required: true,
        description: 'Текст сообщения',
        displayOptions: { show: { operation: ['sendMessage', 'editMessageText'] } },
    },
    // --- Parse Mode ---
    {
        displayName: 'Parse Mode',
        name: 'parseMode',
        type: 'options',
        default: '',
        options: [
            { name: 'Без форматирования', value: '' },
            { name: 'Markdown', value: 'markdown' },
            { name: 'HTML', value: 'html' },
        ],
        description: 'Режим форматирования текста',
        displayOptions: { show: { operation: ['sendMessage', 'editMessageText'] } },
    },
    // --- Reply Markup (inline keyboard) ---
    {
        displayName: 'Reply Markup (JSON)',
        name: 'replyMarkup',
        type: 'json',
        default: '',
        description: 'JSON inline-клавиатуры (Telegram-формат). Пример: {"inline_keyboard":[[{"text":"Кнопка","callback_data":"btn1"}]]}',
        displayOptions: { show: { operation: ['sendMessage', 'editMessageText'] } },
    },
    // --- sendDocument / sendPhoto ---
    {
        displayName: 'Binary Property',
        name: 'binaryProperty',
        type: 'string',
        default: 'data',
        required: true,
        description: 'Имя бинарного свойства с файлом для отправки',
        displayOptions: { show: { operation: ['sendDocument', 'sendPhoto'] } },
    },
    {
        displayName: 'Подпись',
        name: 'caption',
        type: 'string',
        default: '',
        description: 'Подпись к файлу/фото (необязательно)',
        displayOptions: { show: { operation: ['sendDocument', 'sendPhoto'] } },
    },
    // --- getFile / downloadFile ---
    {
        displayName: 'File ID',
        name: 'fileId',
        type: 'string',
        default: '',
        required: true,
        description: 'Идентификатор файла (file_id). Берётся из данных сообщения с файлом',
        displayOptions: { show: { operation: ['getFile', 'downloadFile'] } },
    },
    {
        displayName: 'Binary Property',
        name: 'downloadBinaryProperty',
        type: 'string',
        default: 'data',
        description: 'Имя бинарного свойства, куда будет записан скачанный файл',
        displayOptions: { show: { operation: ['downloadFile'] } },
    },
];
class N8nFront {
    constructor() {
        this.description = {
            displayName: 'N8nFront',
            name: 'n8nFront',
            icon: 'file:n8nfront.svg',
            group: ['output'],
            version: 1,
            subtitle: '={{ $parameter["operation"] }}',
            description: 'Отправка сообщений и файлов через N8nFront Bot API',
            defaults: {
                name: 'N8nFront',
            },
            inputs: ['main'],
            outputs: ['main'],
            credentials: [
                {
                    name: 'n8nFrontApi',
                    required: true,
                },
            ],
            properties: operationFields,
        };
    }
    async execute() {
        const items = this.getInputData();
        const returnData = [];
        const credentials = await this.getCredentials('n8nFrontApi');
        const baseUrl = credentials.baseUrl.replace(/\/+$/, '');
        const botToken = credentials.botToken;
        const apiBase = `${baseUrl}/api/bot/${botToken}`;
        for (let i = 0; i < items.length; i++) {
            const operation = this.getNodeParameter('operation', i);
            try {
                if (operation === 'getMe') {
                    const response = await this.helpers.httpRequest({
                        method: 'GET',
                        url: `${apiBase}/getMe`,
                    });
                    returnData.push({ json: response });
                }
                else if (operation === 'sendMessage') {
                    const chatId = this.getNodeParameter('chatId', i);
                    const text = this.getNodeParameter('text', i);
                    const parseMode = this.getNodeParameter('parseMode', i);
                    const replyMarkup = this.getNodeParameter('replyMarkup', i, '');
                    const body = {
                        chat_id: chatId,
                        text,
                        parse_mode: parseMode,
                    };
                    if (replyMarkup) {
                        body.reply_markup = typeof replyMarkup === 'string'
                            ? JSON.parse(replyMarkup) : replyMarkup;
                    }
                    const response = await this.helpers.httpRequest({
                        method: 'POST',
                        url: `${apiBase}/sendMessage`,
                        body,
                        headers: { 'Content-Type': 'application/json' },
                    });
                    returnData.push({ json: response });
                }
                else if (operation === 'editMessageText') {
                    const chatId = this.getNodeParameter('chatId', i);
                    const messageId = this.getNodeParameter('messageId', i);
                    const text = this.getNodeParameter('text', i);
                    const parseMode = this.getNodeParameter('parseMode', i);
                    const replyMarkup = this.getNodeParameter('replyMarkup', i, '');
                    const body = {
                        chat_id: chatId,
                        message_id: messageId,
                        text,
                        parse_mode: parseMode,
                    };
                    if (replyMarkup) {
                        body.reply_markup = typeof replyMarkup === 'string'
                            ? JSON.parse(replyMarkup) : replyMarkup;
                    }
                    const response = await this.helpers.httpRequest({
                        method: 'POST',
                        url: `${apiBase}/editMessageText`,
                        body,
                        headers: { 'Content-Type': 'application/json' },
                    });
                    returnData.push({ json: response });
                }
                else if (operation === 'deleteMessage') {
                    const chatId = this.getNodeParameter('chatId', i);
                    const messageId = this.getNodeParameter('messageId', i);
                    const response = await this.helpers.httpRequest({
                        method: 'POST',
                        url: `${apiBase}/deleteMessage`,
                        body: {
                            chat_id: chatId,
                            message_id: messageId,
                        },
                        headers: { 'Content-Type': 'application/json' },
                    });
                    returnData.push({ json: response });
                }
                else if (operation === 'sendChatAction') {
                    const chatId = this.getNodeParameter('chatId', i);
                    const response = await this.helpers.httpRequest({
                        method: 'POST',
                        url: `${apiBase}/sendChatAction`,
                        body: {
                            chat_id: chatId,
                            action: 'typing',
                        },
                        headers: { 'Content-Type': 'application/json' },
                    });
                    returnData.push({ json: response });
                }
                else if (operation === 'sendDocument' || operation === 'sendPhoto') {
                    const chatId = this.getNodeParameter('chatId', i);
                    const caption = this.getNodeParameter('caption', i);
                    const binaryProperty = this.getNodeParameter('binaryProperty', i);
                    const binaryData = this.helpers.assertBinaryData(i, binaryProperty);
                    const buffer = await this.helpers.getBinaryDataBuffer(i, binaryProperty);
                    const fieldName = operation === 'sendPhoto' ? 'photo' : 'document';
                    const fileName = binaryData.fileName || 'file';
                    const mimeType = binaryData.mimeType || 'application/octet-stream';
                    const response = await this.helpers.request({
                        method: 'POST',
                        uri: `${apiBase}/${operation}`,
                        formData: {
                            chat_id: chatId,
                            caption,
                            [fieldName]: {
                                value: buffer,
                                options: {
                                    filename: fileName,
                                    contentType: mimeType,
                                },
                            },
                        },
                        json: true,
                    });
                    returnData.push({ json: response });
                }
                else if (operation === 'getFile') {
                    const fileId = this.getNodeParameter('fileId', i);
                    const response = await this.helpers.httpRequest({
                        method: 'GET',
                        url: `${apiBase}/getFile`,
                        qs: { file_id: fileId },
                    });
                    returnData.push({ json: response });
                }
                else if (operation === 'downloadFile') {
                    const fileId = this.getNodeParameter('fileId', i);
                    const binaryProperty = this.getNodeParameter('downloadBinaryProperty', i);
                    // Step 1: get file info
                    const fileInfo = await this.helpers.httpRequest({
                        method: 'GET',
                        url: `${apiBase}/getFile`,
                        qs: { file_id: fileId },
                    });
                    if (!fileInfo.ok || !fileInfo.result?.file_path) {
                        throw new Error(`File not found: ${fileId}`);
                    }
                    // Step 2: download binary
                    const filePath = fileInfo.result.file_path;
                    const downloadUrl = `${apiBase}/${filePath}`;
                    const response = await this.helpers.httpRequest({
                        method: 'GET',
                        url: downloadUrl,
                        encoding: 'arraybuffer',
                        returnFullResponse: true,
                    });
                    const contentType = response.headers?.['content-type'] || 'application/octet-stream';
                    const contentDisposition = response.headers?.['content-disposition'] || '';
                    let fileName = fileId;
                    // Extract filename from Content-Disposition header
                    const filenameMatch = contentDisposition.match(/filename[^;=\n]*=(?:UTF-8''|"?)([^";\n]*)/i);
                    if (filenameMatch) {
                        fileName = decodeURIComponent(filenameMatch[1]);
                    }
                    const binaryData = await this.helpers.prepareBinaryData(Buffer.from(response.body), fileName, contentType);
                    returnData.push({
                        json: fileInfo,
                        binary: { [binaryProperty]: binaryData },
                    });
                }
            }
            catch (error) {
                if (this.continueOnFail()) {
                    returnData.push({
                        json: { error: error.message },
                        pairedItem: { item: i },
                    });
                    continue;
                }
                throw error;
            }
        }
        return [returnData];
    }
}
exports.N8nFront = N8nFront;
//# sourceMappingURL=N8nFront.node.js.map