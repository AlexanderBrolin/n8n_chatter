import type {
	IWebhookFunctions,
	IWebhookResponseData,
	INodeType,
	INodeTypeDescription,
	IHookFunctions,
} from 'n8n-workflow';

export class N8nFrontTrigger implements INodeType {
	description: INodeTypeDescription = {
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
		outputs: ['main'] as any,
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

	webhookMethods = {
		default: {
			async checkExists(this: IHookFunctions): Promise<boolean> {
				const credentials = await this.getCredentials('n8nFrontApi');
				const webhookUrl = this.getNodeWebhookUrl('default');

				try {
					const response = await this.helpers.httpRequest({
						method: 'GET',
						url: `${(credentials.baseUrl as string).replace(/\/+$/, "")}/api/bot/${credentials.botToken}/getWebhookInfo`,
					});
					return response?.result?.url === webhookUrl;
				} catch {
					return false;
				}
			},

			async create(this: IHookFunctions): Promise<boolean> {
				const credentials = await this.getCredentials('n8nFrontApi');
				const webhookUrl = this.getNodeWebhookUrl('default');

				await this.helpers.httpRequest({
					method: 'POST',
					url: `${(credentials.baseUrl as string).replace(/\/+$/, "")}/api/bot/${credentials.botToken}/setWebhook`,
					body: { url: webhookUrl },
					headers: { 'Content-Type': 'application/json' },
				});

				return true;
			},

			async delete(this: IHookFunctions): Promise<boolean> {
				const credentials = await this.getCredentials('n8nFrontApi');

				try {
					await this.helpers.httpRequest({
						method: 'POST',
						url: `${(credentials.baseUrl as string).replace(/\/+$/, "")}/api/bot/${credentials.botToken}/deleteWebhook`,
					});
				} catch {
					// Ignore errors on cleanup
				}

				return true;
			},
		},
	};

	async webhook(this: IWebhookFunctions): Promise<IWebhookResponseData> {
		const body = this.getBodyData() as {
			update_id?: number;
			message?: {
				message_id?: number;
				text?: string;
				from?: { id?: number; first_name?: string; username?: string };
				chat?: { id?: number; type?: string };
				date?: number;
				document?: { file_id?: string; file_name?: string; file_size?: number; mime_type?: string };
				photo?: Array<{ file_id?: string; file_size?: number }>;
				voice?: { file_id?: string; duration?: number; file_size?: number; mime_type?: string };
				video_note?: { file_id?: string; length?: number; duration?: number; file_size?: number };
			};
			callback_query?: {
				id?: string;
				from?: { id?: number; first_name?: string; username?: string };
				message?: Record<string, unknown>;
				chat_instance?: string;
				data?: string;
			};
		};

		const events = this.getNodeParameter('events', []) as string[];

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
